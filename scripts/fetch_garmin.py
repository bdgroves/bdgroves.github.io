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
    sys.exit(0)  # exit clean — keep cached data

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
    sys.exit(0)
except GarminConnectTooManyRequestsError as e:
    print(f"WARN: rate limited — {e}. Leaving cached data untouched.")
    sys.exit(0)
except GarminConnectConnectionError as e:
    print(f"WARN: connection error — {e}. Leaving cached data untouched.")
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

# ─── All-time totals: NOT recomputed daily (would need full history) ───
# Preserved from cache. Seeded once from the last known-good Strava
# all_time snapshot (as of 2026-06-30, the last successful Strava pull
# before the paywall). Will not auto-update from Garmin day to day —
# revisit later with an incremental backfill if this matters more.
# Self-heals: if the cache is missing OR was previously written as all
# zeros (e.g. the very first Garmin run before this seed existed), we
# fall back to the seed instead of perpetuating zeros forever.
ALLTIME_SEED = {
    'run':  {'miles': 11367.2, 'count': 2958},
    'ride': {'miles': 12957.2, 'count': 1008},
    'swim': {'yards': 110108,  'count': 84},
}
cached_alltime = cached.get('all_time')
looks_unseeded = (
    not cached_alltime
    or all(cached_alltime.get(k, {}).get('miles', cached_alltime.get(k, {}).get('yards', 0)) == 0
           for k in ('run', 'ride', 'swim'))
)
alltime_block = ALLTIME_SEED if looks_unseeded else cached_alltime
if looks_unseeded:
    print("All-time cache missing or zeroed — using seed snapshot (2026-06-30)")

# ─── Format recent activities for the site ───
activities = []
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
        'date':      date_str,
        'kudos':     0,  # Garmin has no kudos equivalent
        'map_url':   f"https://connect.garmin.com/modern/activity/{activity_id}" if activity_id else '',
    })

if not activities and cached.get('activities'):
    print("Preserving cached recent activities")
    activities = cached['activities']

# ─────────────────────────────────────────────────────────────────
# PERFORMANCE + READINESS — undocumented/internal Garmin endpoints.
# These aren't publicly documented the way the activities API is, so
# field names below are best-effort. Everything is wrapped defensively:
# if a field isn't where we expect it, we fall back to None/hidden
# rather than crash. We also print the raw top-level keys of each
# response on first run so we can verify/adjust field names for real.
# ─────────────────────────────────────────────────────────────────
today_str = date.today().isoformat()

def sec_to_pace(total_seconds, per_unit_label):
    """Format a race-prediction time (seconds) as H:MM:SS or MM:SS."""
    if not total_seconds:
        return None
    s = int(total_seconds)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

# --- Race predictions ---
race_predictions = None
try:
    rp = client.get_race_predictions()
    print(f"DEBUG race_predictions top-level keys: {list(rp.keys()) if isinstance(rp, dict) else type(rp)}")
    if isinstance(rp, dict):
        race_predictions = {
            '5k':  sec_to_pace(rp.get('predictedTime5K') or rp.get('time5K'), '5k'),
            '10k': sec_to_pace(rp.get('predictedTime10K') or rp.get('time10K'), '10k'),
            'half': sec_to_pace(rp.get('predictedTimeHalfMarathon') or rp.get('timeHalfMarathon'), 'half'),
            'full': sec_to_pace(rp.get('predictedTimeMarathon') or rp.get('timeMarathon'), 'full'),
        }
except Exception as e:
    print(f"WARN: race predictions fetch failed: {e}")

# --- Max metrics (VO2 max + fitness age) ---
vo2max_running = None
vo2max_cycling = None
fitness_age = None
try:
    mm = client.get_max_metrics(today_str)
    print(f"DEBUG max_metrics shape: {type(mm)} — {mm if not isinstance(mm, (list, dict)) else (list(mm.keys()) if isinstance(mm, dict) else f'list of {len(mm)}')}")
    # Response has historically been a list of daily records; be flexible.
    entries = mm if isinstance(mm, list) else ([mm] if isinstance(mm, dict) else [])
    for entry in entries:
        gvm = entry.get('generic', {}).get('vo2MaxPreciseValue') or entry.get('generic', {}).get('vo2MaxValue')
        if gvm:
            vo2max_running = round(gvm)
        cvm = entry.get('cycling', {}).get('vo2MaxPreciseValue') or entry.get('cycling', {}).get('vo2MaxValue')
        if cvm:
            vo2max_cycling = round(cvm)
    try:
        fa = client.get_fitnessage_data(today_str) if hasattr(client, 'get_fitnessage_data') else None
        if isinstance(fa, dict):
            fitness_age = fa.get('fitnessAge') or fa.get('chronologicalAge')
    except Exception as e:
        print(f"WARN: fitness age fetch failed: {e}")
except Exception as e:
    print(f"WARN: max metrics fetch failed: {e}")

# --- Personal records ---
personal_records = []
try:
    prs = client.get_personal_records()
    print(f"DEBUG personal_records shape: {type(prs)} — {len(prs) if isinstance(prs, list) else 'n/a'} entries")
    PR_TYPE_LABELS = {
        1: 'Longest Run', 2: 'Fastest 1K', 3: 'Fastest 5K', 4: 'Fastest 10K',
        7: 'Longest Ride', 8: 'Fastest Half Marathon', 9: 'Fastest Marathon',
        12: 'Most Elevation Gain', 13: 'Longest Swim',
    }
    if isinstance(prs, list):
        for pr in prs[:8]:
            type_id = pr.get('typeId')
            label = PR_TYPE_LABELS.get(type_id, pr.get('prTypeLabel', f'PR {type_id}'))
            value = pr.get('value')
            pr_date = pr.get('prStartTimeGmtFormatted', pr.get('prStartTimeGmt', ''))[:10]
            if value is not None:
                personal_records.append({'label': label, 'value': value, 'date': pr_date})
except Exception as e:
    print(f"WARN: personal records fetch failed: {e}")

# --- Training readiness ---
readiness_score = None
readiness_level = None
try:
    tr = client.get_training_readiness(today_str)
    print(f"DEBUG training_readiness shape: {type(tr)} — {tr if not isinstance(tr, (list, dict)) else (list(tr[0].keys()) if isinstance(tr, list) and tr else (list(tr.keys()) if isinstance(tr, dict) else 'empty'))}")
    entry = tr[0] if isinstance(tr, list) and tr else (tr if isinstance(tr, dict) else None)
    if entry:
        readiness_score = entry.get('score')
        readiness_level = entry.get('level') or entry.get('feedbackShort') or entry.get('feedbackLong')
except Exception as e:
    print(f"WARN: training readiness fetch failed: {e}")

# --- Training status ---
training_status_label = None
try:
    ts = client.get_training_status(today_str)
    print(f"DEBUG training_status shape: {type(ts)} — {list(ts.keys()) if isinstance(ts, dict) else 'n/a'}")
    if isinstance(ts, dict):
        # Nested under mostRecentTrainingStatus in past observations; try a few paths.
        candidates = ts.get('mostRecentTrainingStatus', {})
        if isinstance(candidates, dict):
            latest = candidates.get('latestTrainingStatusData', {})
            if isinstance(latest, dict) and latest:
                first_device = next(iter(latest.values()), {})
                training_status_label = first_device.get('trainingStatusFeedbackPhrase') or first_device.get('trainingStatus')
except Exception as e:
    print(f"WARN: training status fetch failed: {e}")

# --- HRV status ---
hrv_status = None
try:
    hrv = client.get_hrv_data(today_str)
    print(f"DEBUG hrv shape: {type(hrv)} — {list(hrv.keys()) if isinstance(hrv, dict) else 'n/a'}")
    if isinstance(hrv, dict):
        summary = hrv.get('hrvSummary', {})
        hrv_status = summary.get('status') or summary.get('feedbackPhrase')
except Exception as e:
    print(f"WARN: HRV fetch failed: {e}")

# --- Body battery (today) ---
body_battery_today = None
try:
    bb = client.get_body_battery(today_str, today_str)
    print(f"DEBUG body_battery shape: {type(bb)} — {len(bb) if isinstance(bb, list) else 'n/a'} entries")
    if isinstance(bb, list) and bb:
        latest = bb[-1]
        values = latest.get('bodyBatteryValuesArray') or []
        if values:
            # Each entry is typically [timestamp, value] — take the last reading.
            last_point = values[-1]
            body_battery_today = last_point[1] if isinstance(last_point, list) and len(last_point) > 1 else None
        body_battery_today = body_battery_today or latest.get('charged')
except Exception as e:
    print(f"WARN: body battery fetch failed: {e}")

performance_block = {
    'race_predictions': race_predictions,
    'vo2max_running': vo2max_running,
    'vo2max_cycling': vo2max_cycling,
    'fitness_age': fitness_age,
    'personal_records': personal_records,
}
readiness_block = {
    'score': readiness_score,
    'level': readiness_level,
    'training_status': training_status_label,
    'hrv_status': hrv_status,
    'body_battery': body_battery_today,
}
# If everything in a block came back empty, preserve whatever was cached
# rather than overwrite good data with an all-None block.
if not any(performance_block.values()) and cached.get('performance'):
    print("Performance fetch came back empty — preserving cached performance block")
    performance_block = cached['performance']
if not any(v for v in readiness_block.values() if v is not None) and cached.get('readiness'):
    print("Readiness fetch came back empty — preserving cached readiness block")
    readiness_block = cached['readiness']

output = {
    'source':      'garmin',
    'updated':     datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'ytd':         ytd_block,
    'all_time':    alltime_block,
    'activities':  activities,
    'performance': performance_block,
    'readiness':   readiness_block,
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
print(f"  Performance: race_predictions={race_predictions}, vo2max_running={vo2max_running}, fitness_age={fitness_age}, {len(personal_records)} PRs")
print(f"  Readiness: score={readiness_score}, level={readiness_level}, training_status={training_status_label}, hrv={hrv_status}, body_battery={body_battery_today}")
