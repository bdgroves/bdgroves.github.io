#!/usr/bin/env python3
"""
Fetch Garmin Connect training data and write data/training.json.

Run via: pixi run fetch-garmin
(or directly: python3 scripts/fetch_garmin.py, with garminconnect + curl_cffi
installed and GARMIN_TOKENS_JSON set in the environment)

Auth: token-only. Expects a saved Garmin token (see garmin_login_setup.py)
in the GARMIN_TOKENS_JSON environment variable. Never touches a real
Garmin password — if the token is missing or expired, this exits cleanly
and preserves whatever's already in data/training.json.
"""
import json, os, sys, tempfile
from datetime import datetime, timezone, date

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

# ─── Load cached data as fallback ───
cached = {}
try:
    with open('data/training.json', encoding='utf-8') as f:
        cached = json.load(f)
    print(f"Loaded cache: updated {cached.get('updated','?')}")
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"No usable cache: {e}")

# ─── Write the saved token into a tokenstore directory ───
# No email/password ever touches this workflow. If the token is
# missing or expired, login() raises cleanly below and we abort
# without writing garbage — same pattern as the old Strava workflow.
token_json = os.environ.get('GARMIN_TOKENS_JSON', '')
if not token_json.strip():
    print("FATAL: GARMIN_TOKENS_JSON secret is empty or missing")
    print("       Set the secret in repo Settings -> Secrets and variables -> Actions.")
    # Exit non-zero so GitHub Actions marks the run as failed and emails.
    # Cached data/training.json is untouched since we never wrote anything.
    sys.exit(1)

tokendir = tempfile.mkdtemp()
with open(os.path.join(tokendir, 'garmin_tokens.json'), 'w', encoding='utf-8') as f:
    f.write(token_json)

try:
    client = Garmin()  # no email/password — token-only auth
    client.login(tokendir)
    print("Token login OK")
except GarminConnectAuthenticationError as e:
    print(f"FATAL: token rejected — {e}")
    print("       The saved token has likely expired. Re-run the local")
    print("       garmin_login_setup.py script and update the")
    print("       GARMIN_TOKENS_JSON secret with a fresh token.")
    # Exit non-zero so GitHub Actions marks the run as failed and emails you.
    # Cached training.json is untouched — the site just serves stale numbers
    # until the token is refreshed and the next run succeeds.
    sys.exit(1)
except GarminConnectTooManyRequestsError as e:
    print(f"WARN: rate limited — {e}. Leaving cached data untouched.")
    # Exit clean — this is transient, next day's run will likely work.
    sys.exit(0)
except GarminConnectConnectionError as e:
    print(f"WARN: connection error — {e}. Leaving cached data untouched.")
    # Exit clean — network blip, not something to email about.
    sys.exit(0)

def m_to_mi(m): return round((m or 0) * 0.000621371, 1)
def m_to_yd(m): return round((m or 0) * 1.09361)
def sec_to_hm(s):
    s = int(s or 0)
    h = s // 3600
    m = (s % 3600) // 60
    return f"{h}h {m}m"

def categorize(type_key):
    """Map Garmin's activityType.typeKey to our 5 tracked buckets."""
    t = (type_key or '').lower()
    if 'running' in t:
        return 'run'
    if 'cycling' in t or 'biking' in t or t == 'virtual_ride':
        return 'ride'
    if 'swimming' in t:
        return 'swim'
    if t == 'yoga':
        return 'yoga'
    if 'strength' in t:
        return 'strength'
    return None

SPORT_ICONS = {
    'run': '🏃', 'ride': '🚴', 'swim': '🏊',
    'yoga': '🧘', 'strength': '🏋️',
}

# ─── Fetch recent activities (last 10) ───
recent_raw = []
try:
    recent_raw = client.get_activities(0, 10) or []
    print(f"Recent activities: {len(recent_raw)} fetched")
except Exception as e:
    print(f"WARN: recent activities fetch failed: {e}")

# ─── Fetch YTD activities (Jan 1 -> today) for aggregation ───
ytd_raw = []
try:
    jan1 = date(datetime.now().year, 1, 1).isoformat()
    today_str = date.today().isoformat()
    ytd_raw = client.get_activities_by_date(jan1, today_str) or []
    print(f"YTD activities: {len(ytd_raw)} fetched")
except Exception as e:
    print(f"WARN: YTD activities fetch failed: {e}")

if not recent_raw and not ytd_raw:
    print("ABORT: no fresh data acquired — leaving cached data/training.json untouched")
    sys.exit(0)

# ─── Aggregate YTD totals per sport bucket ───
buckets = {
    'run':      {'dist': 0, 'secs': 0, 'count': 0},
    'ride':     {'dist': 0, 'secs': 0, 'count': 0},
    'swim':     {'dist': 0, 'secs': 0, 'count': 0},
    'yoga':     {'dist': 0, 'secs': 0, 'count': 0},
    'strength': {'dist': 0, 'secs': 0, 'count': 0},
}
for a in ytd_raw:
    cat = categorize((a.get('activityType') or {}).get('typeKey'))
    if not cat:
        continue
    buckets[cat]['dist']  += a.get('distance', 0) or 0
    buckets[cat]['secs']  += a.get('duration', 0) or 0
    buckets[cat]['count'] += 1

ytd_block = {
    'run':  {'miles': m_to_mi(buckets['run']['dist']),  'time': sec_to_hm(buckets['run']['secs']),  'count': buckets['run']['count']},
    'ride': {'miles': m_to_mi(buckets['ride']['dist']), 'time': sec_to_hm(buckets['ride']['secs']), 'count': buckets['ride']['count']},
    'swim': {'yards': m_to_yd(buckets['swim']['dist']), 'time': sec_to_hm(buckets['swim']['secs']), 'count': buckets['swim']['count']},
    'yoga': {'count': buckets['yoga']['count'], 'time': sec_to_hm(buckets['yoga']['secs'])},
    'strength': {'count': buckets['strength']['count'], 'time': sec_to_hm(buckets['strength']['secs'])},
}

# ─── All-time totals: incremental, not recomputed from scratch ───
# A one-time backfill (garmin_backfill_alltime.py) establishes the true
# baseline + a "counted_through" marker (the newest activity ID already
# folded in). Each daily run only needs to look at activities newer than
# that marker and add them in — no need to ever re-paginate full history.
# Falls back to the old frozen Strava-era seed only if no backfill has
# been run yet at all.
ALLTIME_SEED = {
    'run':  {'miles': 11367.2, 'count': 2958},
    'ride': {'miles': 12957.2, 'count': 1008},
    'swim': {'yards': 110108,  'count': 84},
}
cached_alltime = cached.get('all_time')
counted_through_id = cached.get('all_time_counted_through_id')

if not cached_alltime or all(
    cached_alltime.get(k, {}).get('miles', cached_alltime.get(k, {}).get('yards', 0)) == 0
    for k in ('run', 'ride', 'swim')
):
    print("All-time cache missing or zeroed — using frozen seed until a backfill is run")
    alltime_block = ALLTIME_SEED
    counted_through_id = None
else:
    alltime_block = {k: dict(v) for k, v in cached_alltime.items()}  # copy, don't mutate cache in place

    # Fold in any activity newer than the last counted one. YTD activities
    # already cover the whole current year, which is always a superset of
    # "since last run" in practice (workflow runs daily), so we reuse that
    # fetch rather than pulling a separate window.
    new_run_dist = new_ride_dist = new_swim_dist = 0
    new_run_n = new_ride_n = new_swim_n = 0
    newest_seen_id = counted_through_id
    newest_seen_date = cached.get('all_time_counted_through_date', '')

    for a in ytd_raw:
        act_id = a.get('activityId')
        if counted_through_id is not None and act_id is not None and act_id <= counted_through_id:
            continue  # already counted in a previous run
        cat = categorize((a.get('activityType') or {}).get('typeKey'))
        dist = a.get('distance', 0) or 0
        if cat == 'run':
            new_run_dist += dist; new_run_n += 1
        elif cat == 'ride':
            new_ride_dist += dist; new_ride_n += 1
        elif cat == 'swim':
            new_swim_dist += dist; new_swim_n += 1
        if act_id is not None and (newest_seen_id is None or act_id > newest_seen_id):
            newest_seen_id = act_id
            newest_seen_date = a.get('startTimeLocal', newest_seen_date)

    if new_run_n or new_ride_n or new_swim_n:
        alltime_block['run']['miles']  = round(alltime_block['run']['miles']  + m_to_mi(new_run_dist), 1)
        alltime_block['run']['count'] += new_run_n
        alltime_block['ride']['miles'] = round(alltime_block['ride']['miles'] + m_to_mi(new_ride_dist), 1)
        alltime_block['ride']['count'] += new_ride_n
        alltime_block['swim']['yards'] = alltime_block['swim']['yards'] + m_to_yd(new_swim_dist)
        alltime_block['swim']['count'] += new_swim_n
        print(f"All-time incremented: +{new_run_n} runs, +{new_ride_n} rides, +{new_swim_n} swims "
              f"(newest activity id now {newest_seen_id})")
    counted_through_id = newest_seen_id
    cached['all_time_counted_through_date'] = newest_seen_date  # carried into output below

# ─── Format recent activities for the site ───
activities = []
if recent_raw:
    sample_keys = set(recent_raw[0].keys())
    print(f"DEBUG activity fields available: {sorted(sample_keys)}")
for a in recent_raw:
    type_key = (a.get('activityType') or {}).get('typeKey', '')
    cat = categorize(type_key)
    dist_m = a.get('distance', 0) or 0
    if cat == 'swim':
        dist_str = f"{m_to_yd(dist_m):,} yd" if dist_m else ''
    else:
        dist_str = f"{m_to_mi(dist_m)} mi" if dist_m else ''
    move_secs = a.get('duration', 0) or 0
    h = int(move_secs) // 3600; m = (int(move_secs) % 3600) // 60; s = int(move_secs) % 60
    time_str = f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"
    pace_str = ''
    if cat == 'run' and dist_m > 0 and move_secs > 0:
        pace_secs = move_secs / (dist_m * 0.000621371)
        pm = int(pace_secs // 60); ps = int(pace_secs % 60)
        pace_str = f"{pm}:{ps:02d}/mi"
    elev_m = a.get('elevationGain', 0) or 0
    avg_hr = a.get('avgHR') or a.get('averageHR')
    hr_str = f"{round(avg_hr)} bpm" if avg_hr else ''
    calories = a.get('calories')
    cal_str = f"{round(calories):,} cal" if calories else ''
    start = a.get('startTimeLocal', '')
    try:
        dt = datetime.fromisoformat(start.replace('Z',''))
        date_str = dt.strftime('%b %d')
    except Exception:
        date_str = ''
    activity_id = a.get('activityId')
    activities.append({
        'id':        activity_id,
        'name':      a.get('activityName', 'Activity'),
        'sport':     type_key,
        'icon':      SPORT_ICONS.get(cat, '⚡'),
        'distance':  dist_str,
        'time':      time_str,
        'pace':      pace_str,
        'elevation': f"{round(elev_m * 3.28084)} ft" if elev_m else '',
        'hr':        hr_str,
        'calories':  cal_str,
        'date':      date_str,
        'kudos':     0,  # Garmin has no kudos equivalent
        'map_url':   f"https://connect.garmin.com/modern/activity/{activity_id}" if activity_id else '',
    })

if not activities and cached.get('activities'):
    print("Preserving cached recent activities")
    activities = cached['activities']

output = {
    'source':                       'garmin',
    'updated':                      datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'ytd':                          ytd_block,
    'all_time':                     alltime_block,
    'all_time_counted_through_id':   counted_through_id,
    'all_time_counted_through_date': cached.get('all_time_counted_through_date', ''),
    'activities':                   activities,
}

os.makedirs('data', exist_ok=True)
with open('data/training.json', 'w') as f:
    json.dump(output, f, indent=2)

print(f"data/training.json written — {len(activities)} recent activities")
print(f"  YTD Run: {ytd_block['run']['miles']} mi · {ytd_block['run']['count']} runs")
print(f"  YTD Ride: {ytd_block['ride']['miles']} mi · {ytd_block['ride']['count']} rides")
print(f"  YTD Swim: {ytd_block['swim']['yards']} yd · {ytd_block['swim']['count']} swims")
print(f"  YTD Yoga: {ytd_block['yoga']['count']} sessions")
print(f"  YTD Strength: {ytd_block['strength']['count']} sessions")
print(f"  All-Time Run: {alltime_block['run']['miles']} mi · {alltime_block['run']['count']} activities")
print(f"  All-Time Ride: {alltime_block['ride']['miles']} mi · {alltime_block['ride']['count']} activities")
print(f"  All-Time Swim: {alltime_block['swim']['yards']} yd · {alltime_block['swim']['count']} activities")
