#!/usr/bin/env python3
"""
ONE-TIME BACKFILL — run this locally, not in CI.

Paginates through your ENTIRE Garmin activity history (all ~15 years of it)
to compute genuinely accurate all-time totals, replacing the frozen Strava
snapshot that's been sitting in data/training.json since the migration.

After this runs once, the daily fetch_garmin.py script takes over and keeps
these totals current incrementally (a few new activities added each day)
rather than ever needing to re-paginate the full history again.

Usage:
    pixi run python garmin_backfill_alltime.py

Safe to re-run — it always recomputes from scratch and overwrites the
all_time block + counted_through marker in data/training.json.
"""
import json
import os
import sys
import time
from datetime import datetime

from garminconnect import Garmin, GarminConnectAuthenticationError, GarminConnectConnectionError

TOKEN_DIR = os.path.expanduser("~/.garminconnect")
# Fall back to the same local folder the login setup script used, if present
if not os.path.exists(TOKEN_DIR):
    local_fallback = "./garmin_tokens_output"
    if os.path.exists(local_fallback):
        TOKEN_DIR = local_fallback

print(f"Using token store: {TOKEN_DIR}")

try:
    client = Garmin()
    client.login(TOKEN_DIR)
    print("Login OK")
except (GarminConnectAuthenticationError, GarminConnectConnectionError) as e:
    print(f"FATAL: login failed: {e}")
    print("Run garmin_login_setup.py first, or point TOKEN_DIR at your saved token folder.")
    sys.exit(1)


def categorize(type_key):
    """Same bucket logic as scripts/fetch_garmin.py — keep these in sync."""
    t = (type_key or '').lower()
    if 'running' in t:
        return 'run'
    if 'cycling' in t or 'biking' in t or t == 'virtual_ride':
        return 'ride'
    if 'swimming' in t:
        return 'swim'
    return None


def m_to_mi(m): return round((m or 0) * 0.000621371, 1)
def m_to_yd(m): return round((m or 0) * 1.09361)


print("Paginating through full activity history — this may take a few minutes...")
buckets = {
    'run':  {'dist': 0, 'count': 0},
    'ride': {'dist': 0, 'count': 0},
    'swim': {'dist': 0, 'count': 0},
}
newest_id = None
newest_date = None
start = 0
page_size = 100
total_seen = 0

while True:
    try:
        batch = client.get_activities(start, page_size)
    except Exception as e:
        print(f"WARN: page fetch failed at start={start}: {e}")
        break
    if not batch:
        break
    for a in batch:
        cat = categorize((a.get('activityType') or {}).get('typeKey'))
        if cat:
            buckets[cat]['dist']  += a.get('distance', 0) or 0
            buckets[cat]['count'] += 1
        # Track the single most recent activity ID/date across all pages
        # (first page, first entry, assuming newest-first ordering)
        if newest_id is None:
            newest_id = a.get('activityId')
            newest_date = a.get('startTimeLocal', '')
    total_seen += len(batch)
    print(f"  ...{total_seen} activities scanned (page start={start})")
    start += page_size
    time.sleep(0.3)  # be polite to Garmin's servers

print(f"\nDone. Scanned {total_seen} total activities.")
print(f"  Run:  {m_to_mi(buckets['run']['dist'])} mi across {buckets['run']['count']} activities")
print(f"  Ride: {m_to_mi(buckets['ride']['dist'])} mi across {buckets['ride']['count']} activities")
print(f"  Swim: {m_to_yd(buckets['swim']['dist'])} yd across {buckets['swim']['count']} activities")
print(f"  Newest activity: id={newest_id}, date={newest_date}")

# --- Write into data/training.json (assumes run from repo root) ---
path = 'data/training.json'
try:
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    data = {}

data['all_time'] = {
    'run':  {'miles': m_to_mi(buckets['run']['dist']),  'count': buckets['run']['count']},
    'ride': {'miles': m_to_mi(buckets['ride']['dist']), 'count': buckets['ride']['count']},
    'swim': {'yards': m_to_yd(buckets['swim']['dist']), 'count': buckets['swim']['count']},
}
data['all_time_counted_through_id'] = newest_id
data['all_time_counted_through_date'] = newest_date
data['all_time_backfilled_at'] = datetime.now().isoformat()

os.makedirs('data', exist_ok=True)
with open(path, 'w') as f:
    json.dump(data, f, indent=2)

print(f"\nWritten to {path}.")
print("Commit and push this file — the daily workflow will take it from here")
print("and keep all_time current incrementally.")
