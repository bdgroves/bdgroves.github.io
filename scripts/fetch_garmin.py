#!/usr/bin/env python3
"""
Fetch Garmin Connect training data and write data/training.json.

Run via: pixi run fetch-garmin
(or directly: python3 scripts/fetch_garmin.py, with garminconnect + curl_cffi
installed and GARMIN_TOKENS_JSON set in the environment)

Auth: token-only. Expects the portable token string produced by
garmin_login_setup.py (repo root) in the GARMIN_TOKENS_JSON environment
variable. Never touches a real Garmin password — if the token is missing
or expired, this exits cleanly and preserves data/training.json.

The token string is a base64 blob carrying BOTH halves of Garmin's auth:
the long-lived OAuth1 token (good for roughly a year) and the short-lived
OAuth2 token. Both must travel together — with the OAuth1 half present the
library mints a fresh OAuth2 on every run, so the secret keeps working for
months. If only the OAuth2 half is stored, its refresh token dies in about
a week and the secret has to be replaced constantly.
"""
import base64, json, os, sys, tempfile
from datetime import datetime, timezone, date, timedelta

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

token_json = token_json.strip()


def _jwt_exp(tok):
    """Read the exp claim out of a JWT without verifying it. Local only."""
    try:
        payload = tok.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return claims.get("exp")
    except Exception:
        return None


def describe_di(tok):
    """Report on Garmin's DI (Digital Identity) token format.

    This is the modern format: di_token is a short-lived JWT Bearer token and
    di_refresh_token is exchanged for a new one. There is no OAuth1 half here
    at all, so its absence is not a fault.
    """
    exp = _jwt_exp(tok.get("di_token") or "")
    has_refresh = bool(tok.get("di_refresh_token"))
    if exp:
        when = datetime.fromtimestamp(exp, tz=timezone.utc)
        mins = (when - datetime.now(timezone.utc)).total_seconds() / 60
        print(f"   di_token expires {when:%Y-%m-%d %H:%M} UTC ({mins:.0f} min)")
    print(f"   di_refresh_token: {'present' if has_refresh else 'MISSING'}")
    return has_refresh


def describe_token(blob):
    """Report what's in the token and when it runs out.

    Handles both formats this repo has seen: Garmin's current DI tokens
    (di_token + di_refresh_token) and the older OAuth1/OAuth2 pair.
    Best-effort and never fatal — diagnostics, not auth.
    Returns days remaining where that is knowable, else None.
    """
    # DI format: plain JSON dict
    try:
        tok = json.loads(blob)
        if isinstance(tok, dict) and "di_token" in tok:
            print("Token: Garmin DI format")
            describe_di(tok)
            return None
    except Exception:
        pass

    # Older portable OAuth1+OAuth2 pair, base64-encoded
    try:
        parts = json.loads(base64.b64decode(blob))
    except Exception:
        print("NOTE: token is in an unrecognised format. Re-run")
        print("      garmin_login_setup.py to regenerate it.")
        return None

    has_oauth1 = isinstance(parts, list) and len(parts) >= 1 and 'oauth_token' in (parts[0] or {})
    oauth2 = parts[1] if isinstance(parts, list) and len(parts) > 1 else {}
    exp = oauth2.get('refresh_token_expires_at')
    if exp:
        when = datetime.fromtimestamp(exp, tz=timezone.utc)
        days = (when - datetime.now(timezone.utc)).days
        print(f"Token: OAuth1 {'present' if has_oauth1 else 'missing'} | "
              f"OAuth2 refresh valid until {when:%Y-%m-%d} ({days}d)")
        return days
    print(f"Token: OAuth1 {'present' if has_oauth1 else 'missing'}")
    return None


days_left = describe_token(token_json)

try:
    client = Garmin()  # no email/password — token-only auth
    tokendir = tempfile.mkdtemp()

    # The library reads two files — oauth1_token.json and oauth2_token.json.
    # The old code wrote a single garmin_tokens.json, which it never looks for.
    # Unpack the portable blob into the two files it actually expects. Doing
    # it explicitly (rather than relying on login()'s >512-character
    # pass-the-string-directly heuristic) means this works whatever the
    # token's length happens to be.
    unpacked = False
    try:
        parts = json.loads(base64.b64decode(token_json))
        if isinstance(parts, list) and len(parts) == 2:
            with open(os.path.join(tokendir, 'oauth1_token.json'), 'w', encoding='utf-8') as f:
                json.dump(parts[0], f)
            with open(os.path.join(tokendir, 'oauth2_token.json'), 'w', encoding='utf-8') as f:
                json.dump(parts[1], f)
            unpacked = True
    except Exception:
        pass

    if not unpacked:
        # Legacy single-file secret. Written so the failure below is a clean
        # auth error with instructions rather than a confusing traceback.
        with open(os.path.join(tokendir, 'garmin_tokens.json'), 'w', encoding='utf-8') as f:
            f.write(token_json)

    client.login(tokendir)
    print("Token login OK")
    if days_left is not None and days_left <= 21:
        print(f"NOTICE: token refresh window has {days_left} days left — "
              f"re-run garmin_login_setup.py soon.")
except GarminConnectAuthenticationError as e:
    print(f"FATAL: token rejected — {e}")
    print("       Re-run garmin_login_setup.py (in the repo root) and update")
    print("       the GARMIN_TOKENS_JSON secret with the string it prints.")
    print("       Settings -> Secrets and variables -> Actions.")
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

# How far back to collect badges, and how many to keep in the JSON.
# The page decides how many of these to actually display — the data layer
# just needs enough for a count and a "+N more".
BADGE_WINDOW_DAYS = 30
BADGE_MAX = 40

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
    'run':      {'dist': 0, 'secs': 0, 'count': 0, 'cal': 0},
    'ride':     {'dist': 0, 'secs': 0, 'count': 0, 'cal': 0},
    'swim':     {'dist': 0, 'secs': 0, 'count': 0, 'cal': 0},
    'yoga':     {'dist': 0, 'secs': 0, 'count': 0, 'cal': 0},
    'strength': {'dist': 0, 'secs': 0, 'count': 0, 'cal': 0},
}

# ─── Beers burned ───────────────────────────────────────────────────────
# A pint of IPA, in calories. 300 is deliberately on the high side: the
# formula (oz x ABV% x 2.5) puts a 16oz 6.5% West Coast IPA nearer 260,
# and 300 matches a 7.5-8% fresh-hop or hazy. Erring high means the pint
# count is conservative — better to under-claim than over-claim.
# Change this one number to re-scale every beer figure on the site.
BEER_CAL = 300

# Calories are summed from two windows: the full year, and a rolling 30
# days. The 30-day figure exists so the page can compare burned against
# Untappd check-ins over the SAME period — Untappd's RSS feed only carries
# the last 20 check-ins, so a year-long drinking total doesn't exist and
# comparing it against a year of exercise would be meaningless.
cal_30d = 0
cutoff_30d = date.today() - timedelta(days=30)

# Per-month totals, so the card can show the shape of the year rather
# than one lump sum. Keyed "YYYY-MM" and emitted in calendar order with
# no gaps — a month with no training still gets a zero row, because a
# missing bar and a zero bar mean different things and only one of them
# is true.
cal_by_month = {}

# Every activity with calories, not just the five categorised sports —
# a walk or a hike burns real calories and should count toward the pint.
cal_ytd_all = 0

for a in ytd_raw:
    cal = a.get('calories', 0) or 0
    cal_ytd_all += cal

    # startTimeLocal looks like "2026-09-21 13:53:29"
    started = (a.get('startTimeLocal') or '')[:10]
    if started:
        try:
            d_ = datetime.strptime(started, '%Y-%m-%d').date()
            if d_ >= cutoff_30d:
                cal_30d += cal
            cal_by_month[f"{d_.year:04d}-{d_.month:02d}"] = \
                cal_by_month.get(f"{d_.year:04d}-{d_.month:02d}", 0) + cal
        except ValueError:
            pass

    cat = categorize((a.get('activityType') or {}).get('typeKey'))
    if not cat:
        continue
    buckets[cat]['dist']  += a.get('distance', 0) or 0
    buckets[cat]['secs']  += a.get('duration', 0) or 0
    buckets[cat]['count'] += 1
    buckets[cat]['cal']   += cal

ytd_block = {
    'run':  {'miles': m_to_mi(buckets['run']['dist']),  'time': sec_to_hm(buckets['run']['secs']),  'count': buckets['run']['count'],  'calories': round(buckets['run']['cal'])},
    'ride': {'miles': m_to_mi(buckets['ride']['dist']), 'time': sec_to_hm(buckets['ride']['secs']), 'count': buckets['ride']['count'], 'calories': round(buckets['ride']['cal'])},
    'swim': {'yards': m_to_yd(buckets['swim']['dist']), 'time': sec_to_hm(buckets['swim']['secs']), 'count': buckets['swim']['count'], 'calories': round(buckets['swim']['cal'])},
    'yoga': {'count': buckets['yoga']['count'], 'time': sec_to_hm(buckets['yoga']['secs']), 'calories': round(buckets['yoga']['cal'])},
    'strength': {'count': buckets['strength']['count'], 'time': sec_to_hm(buckets['strength']['secs']), 'calories': round(buckets['strength']['cal'])},
}

MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
today_ = date.today()
months = []
for mo in range(1, today_.month + 1):
    c = round(cal_by_month.get(f"{today_.year:04d}-{mo:02d}", 0))
    months.append({
        'month':    MONTH_NAMES[mo - 1],
        'calories': c,
        'pints':    round(c / BEER_CAL, 1),
    })

# ─── Daily TSS series, for FuelCast's training-load model ───────────────
# FuelCast computes CTL/ATL/TSB from daily TSS. Its own source is the
# TrainingPeaks iCal feed, which only exposes a short window — so every
# day outside that window was being counted as TSS 0 and decaying a
# legitimate CTL toward nothing. Garmin has the real history; this emits
# it in the shape FuelCast's load model already expects.
#
# Two ways to get TSS, in order of trust:
#
#  1. Garmin's own activityTrainingLoad. EPOC-derived, computed on-watch
#     from HR against the athlete's own profile. Scale is comparable to
#     TSS and it is the closest thing to ground truth available here.
#  2. Duration x a per-sport rate. Used only when Garmin gives no load
#     value. Deliberately conservative — under-stating fitness is the
#     safer error, because over-stating it suppresses the recovery
#     warnings the whole tool exists to raise.
#
# HR-derived TSS is deliberately NOT attempted: athlete.yaml records
# hr_data_source as chest_strap_only with max_hr unset, so wrist HR here
# cannot be trusted and there is no threshold to compute against.
TSS_PER_HOUR = {
    'run':      55,
    'ride':     50,
    'swim':     45,
    'strength': 20,   # matches FuelCast's existing strength convention
    'yoga':     10,
    None:       15,   # uncategorised (walks, hikes) — FuelCast's own floor
}
TSS_WINDOW_DAYS = 180

tss_by_day = {}
tss_src = {'garmin': 0, 'estimated': 0, 'skipped': 0}
tss_cutoff = date.today() - timedelta(days=TSS_WINDOW_DAYS)

for a in ytd_raw:
    started = (a.get('startTimeLocal') or '')[:10]
    if not started:
        tss_src['skipped'] += 1
        continue
    try:
        d_ = datetime.strptime(started, '%Y-%m-%d').date()
    except ValueError:
        tss_src['skipped'] += 1
        continue
    if d_ < tss_cutoff:
        continue

    load = a.get('activityTrainingLoad')
    if load:
        tss = float(load)
        tss_src['garmin'] += 1
    else:
        secs = a.get('duration', 0) or 0
        if secs <= 0:
            tss_src['skipped'] += 1
            continue
        cat = categorize((a.get('activityType') or {}).get('typeKey'))
        tss = TSS_PER_HOUR.get(cat, TSS_PER_HOUR[None]) * (secs / 3600.0)
        tss_src['estimated'] += 1

    tss_by_day[d_.isoformat()] = tss_by_day.get(d_.isoformat(), 0.0) + tss

# Emit every day in the window, including zeros. A rest day and a missing
# day are different facts and the load model must not confuse them — that
# confusion is exactly what produced the bad CTL in the first place.
daily_tss = []
_d = tss_cutoff
while _d <= date.today():
    daily_tss.append({'date': _d.isoformat(), 'tss': round(tss_by_day.get(_d.isoformat(), 0.0), 1)})
    _d += timedelta(days=1)

_active = [x for x in daily_tss if x['tss'] > 0]
_mean = round(sum(x['tss'] for x in daily_tss) / max(len(daily_tss), 1), 1)
tss_block = {
    'window_days':   TSS_WINDOW_DAYS,
    'start':         daily_tss[0]['date'],
    'end':           daily_tss[-1]['date'],
    'method':        'garmin_activityTrainingLoad_with_duration_fallback',
    'from_garmin':   tss_src['garmin'],
    'estimated':     tss_src['estimated'],
    'skipped':       tss_src['skipped'],
    'active_days':   len(_active),
    'mean_daily':    _mean,
    'daily':         daily_tss,
}
print(f"Daily TSS: {len(daily_tss)} days, {len(_active)} active, mean {_mean}/day "
      f"({tss_src['garmin']} from Garmin load, {tss_src['estimated']} estimated, "
      f"{tss_src['skipped']} skipped)")
if tss_src['garmin'] == 0 and tss_src['estimated'] > 0:
    print("  NOTE: activityTrainingLoad absent on every activity — all TSS is "
          "duration-estimated. Check the DEBUG field list below.")

# ─── Athlete state: body composition, energy, recovery ──────────────────
# FuelCast sizes every macro per kg and — once it has an energy model —
# needs to know what the athlete actually burns. Both used to be guesses:
# weight was a hand-edited number in athlete.yaml ("update monthly"), and
# expenditure wasn't modelled at all. Garmin measures both. This publishes
# them for the FuelCast repo to consume.
#
# Everything here is best-effort. Each section fails independently and a
# missing section makes FuelCast fall back to its configured values, which
# is exactly what it did before this existed. Nothing here can break the
# dashboard.

def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None

def _slope_per_week(points):
    """Least-squares slope of (date, value) pairs, in units per week.
    Requires >=4 points over >=10 days — fewer produces a confident trend
    out of two noisy readings, which is worse than no trend."""
    if len(points) < 4 or (points[-1][0] - points[0][0]).days < 10:
        return None
    x0 = points[0][0]
    xs = [(d - x0).days for d, _ in points]
    ys = [v for _, v in points]
    n = len(xs); mx = sum(xs) / n; my = sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den <= 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den * 7

athlete_state = {}

# ── 1. Body composition (Index scale) ─────────────────────────────────
# Three weight numbers, because one day's reading is close to useless —
# scale weight swings a kilo on hydration and glycogen alone:
#   latest   — reference only
#   smoothed — 7-day mean; what should drive per-kg macros
#   trend    — 30-day least-squares slope; the only honest answer to
#              "is the plan working"
# Body fat gives fat-free mass, which is the correct denominator for
# energy availability (the RED-S safety floor), not total weight.
try:
    w_start = (date.today() - timedelta(days=90)).isoformat()
    body = client.get_body_composition(w_start, date.today().isoformat()) or {}
    rows = body.get('dateWeightList') or []
    per_day = {}
    for r in rows:
        g = r.get('weight')
        cal = r.get('calendarDate') or (str(r.get('date'))[:10] if r.get('date') else None)
        if not g or not cal:
            continue
        try:
            d_ = datetime.strptime(str(cal)[:10], '%Y-%m-%d').date()
        except ValueError:
            continue
        bf = r.get('bodyFat')
        mm = r.get('muscleMass')
        per_day.setdefault(d_, {'kg': [], 'bf': [], 'mm': []})
        per_day[d_]['kg'].append(float(g) / 1000.0)
        if bf: per_day[d_]['bf'].append(float(bf))
        if mm: per_day[d_]['mm'].append(float(mm) / 1000.0)

    days_sorted = sorted(per_day)
    if days_sorted:
        daily_kg = [(d, _mean(per_day[d]['kg'])) for d in days_sorted]
        daily_bf = [(d, _mean(per_day[d]['bf'])) for d in days_sorted if per_day[d]['bf']]
        latest_d, latest_kg = daily_kg[-1]
        recent7 = [kg for d, kg in daily_kg if (date.today() - d).days < 7]
        smoothed = _mean(recent7) or latest_kg
        trend = _slope_per_week([(d, kg) for d, kg in daily_kg
                                 if (date.today() - d).days <= 30])
        bf_recent = [bf for d, bf in daily_bf if (date.today() - d).days < 14]
        bf_pct = _mean(bf_recent)
        ffm = smoothed * (1 - bf_pct / 100) if bf_pct else None

        athlete_state['weight'] = {
            'latest_kg':         round(latest_kg, 1),
            'latest_date':       latest_d.isoformat(),
            'smoothed_kg':       round(smoothed, 1),
            'smoothed_lb':       round(smoothed * 2.20462, 1),
            'trend_kg_per_week': round(trend, 2) if trend is not None else None,
            'trend_lb_per_week': round(trend * 2.20462, 2) if trend is not None else None,
            'body_fat_pct':      round(bf_pct, 1) if bf_pct else None,
            'ffm_kg':            round(ffm, 1) if ffm else None,
            'readings':          len(daily_kg),
            'stale_days':        (date.today() - latest_d).days,
        }
        w_ = athlete_state['weight']
        print(f"Weight: {w_['smoothed_lb']} lb (7d mean), trend "
              f"{w_['trend_lb_per_week']} lb/wk, body fat {w_['body_fat_pct']}%, "
              f"FFM {w_['ffm_kg']} kg, {w_['readings']} readings")
    else:
        print("WARN: no weigh-ins in 90 days — is the Index scale syncing?")
except Exception as e:
    print(f"WARN: body composition fetch failed ({type(e).__name__}: {e})")

# ── 2. Measured daily energy expenditure ──────────────────────────────
# Garmin reports total, active and BMR kilocalories per day from the
# watch. That is a measured TDEE, and a far better input than any
# predictive equation.
#
# Completed days only. This job runs at 08:00 UTC, which is ~01:00
# Pacific — "today" has barely started, and averaging it in would drag
# expenditure down by a third. Days with near-zero steps are dropped too:
# that's the watch on the charger, not a rest day, and Garmin fills those
# with BMR alone.
ENERGY_DAYS = 14
try:
    energy_rows = []
    for i in range(1, ENERGY_DAYS + 1):
        d_ = date.today() - timedelta(days=i)
        try:
            st = client.get_stats(d_.isoformat()) or {}
        except Exception:
            continue
        total = st.get('totalKilocalories')
        steps = st.get('totalSteps') or 0
        if not total or steps < 200:
            continue
        energy_rows.append({
            'date':   d_.isoformat(),
            'total':  round(total),
            'active': round(st.get('activeKilocalories') or 0),
            'bmr':    round(st.get('bmrKilocalories') or 0),
            'steps':  steps,
            'rhr':    st.get('restingHeartRate'),
        })
    energy_rows.sort(key=lambda r: r['date'])

    if energy_rows:
        last7 = energy_rows[-7:]
        # Training calories over the same 7 complete days, net of the BMR
        # the athlete would have burned anyway during the session. The model
        # needs this to split the measured TDEE into "baseline" and
        # "training" — otherwise today's session gets counted twice, once
        # inside the average and once on top of it.
        bmr_day = _mean([r['bmr'] for r in last7 if r['bmr']]) or 1750
        bmr_per_min = bmr_day / 1440.0
        window = {r['date'] for r in last7}
        train_by_day = {}
        for a in ytd_raw:
            dstr = (a.get('startTimeLocal') or '')[:10]
            if dstr not in window:
                continue
            gross = a.get('calories') or 0
            mins = (a.get('duration') or 0) / 60.0
            bmr_share = a.get('bmrCalories') or bmr_per_min * mins
            train_by_day[dstr] = train_by_day.get(dstr, 0) + max(0, gross - bmr_share)
        training_7d = sum(train_by_day.values()) / len(last7)

        # Net kcal per hour by sport, from this athlete's own YTD history.
        # Brooks's "runs" include a lot of walking, so a textbook running
        # rate would overstate them badly; his own numbers don't.
        rates = {}
        for cat in ('run', 'ride', 'swim', 'strength', 'yoga'):
            hrs = buckets[cat]['secs'] / 3600.0
            if hrs >= 2:
                gross_hr = buckets[cat]['cal'] / hrs
                rates[cat] = round(max(0, gross_hr - bmr_day / 24.0))

        athlete_state['energy'] = {
            'tdee_7d':          round(_mean([r['total'] for r in last7])),
            'active_7d':        round(_mean([r['active'] for r in last7])),
            'bmr':              round(bmr_day),
            'training_kcal_7d': round(training_7d),
            'kcal_per_hour':    rates,
            'tdee_14d':         round(_mean([r['total'] for r in energy_rows])),
            'days':             len(energy_rows),
            'daily':            energy_rows,
        }
        e_ = athlete_state['energy']
        print(f"Energy: TDEE {e_['tdee_7d']} kcal/day (7d), training {e_['training_kcal_7d']}, "
              f"BMR {e_['bmr']}, from {e_['days']} complete days")
        print(f"  net kcal/hr: " + ", ".join(f"{k} {v}" for k, v in rates.items()))
    else:
        print("WARN: no complete days of energy data")
except Exception as e:
    print(f"WARN: daily stats fetch failed ({type(e).__name__}: {e})")

# ── 3. Recovery signals ───────────────────────────────────────────────
# Resting HR and overnight HRV, as context only. FuelCast shows them; it
# does not prescribe from them. athlete.yaml records wrist optical HR as
# unreliable during exercise — overnight resting values are a different
# and much easier measurement, but they're labelled as wrist-derived so
# nothing downstream mistakes them for chest-strap data.
try:
    rec = {'source': 'wrist_optical_overnight'}
    rhrs = [r['rhr'] for r in athlete_state.get('energy', {}).get('daily', []) if r.get('rhr')]
    if rhrs:
        rec['rhr_last'] = rhrs[-1]
        rec['rhr_7d'] = round(_mean(rhrs[-7:]), 1)
        rec['rhr_14d'] = round(_mean(rhrs), 1)
    # HRV is its own call and its own failure. Wrapping it together with
    # RHR meant an HRV outage silently discarded RHR too, even though RHR
    # came from a different endpoint that had already succeeded.
    try:
        hrv = client.get_hrv_data((date.today() - timedelta(days=1)).isoformat()) or {}
        hs = hrv.get('hrvSummary') or {}
        if hs:
            base = hs.get('baseline') or {}
            rec['hrv_last_night'] = hs.get('lastNightAvg')
            rec['hrv_7d'] = hs.get('weeklyAvg')
            rec['hrv_status'] = hs.get('status')          # BALANCED / UNBALANCED / LOW
            rec['hrv_baseline_low'] = base.get('balancedLow')
            rec['hrv_baseline_high'] = base.get('balancedUpper')
    except Exception as e:
        print(f"WARN: HRV fetch failed ({type(e).__name__}: {e}) — keeping RHR")
    if len(rec) > 1:
        athlete_state['recovery'] = rec
        print(f"Recovery: RHR {rec.get('rhr_7d')} (7d), HRV {rec.get('hrv_last_night')} "
              f"last night, status {rec.get('hrv_status')}")
except Exception as e:
    print(f"WARN: recovery fetch failed ({type(e).__name__}: {e})")


# ─── What a pint costs, in your own units ───────────────────────────────
# Derived from this athlete's actual YTD calories-per-mile, not a generic
# table: run and ride rates differ by more than 2x, and both drift with
# fitness over a season. Guarded against divide-by-zero in January.
run_mi   = m_to_mi(buckets['run']['dist'])
ride_mi  = m_to_mi(buckets['ride']['dist'])
cal_mile_run  = round(buckets['run']['cal']  / run_mi, 1)  if run_mi  >= 1 else None
cal_mile_ride = round(buckets['ride']['cal'] / ride_mi, 1) if ride_mi >= 1 else None

def _pints(miles, rate):
    return round(miles * rate / BEER_CAL, 1) if rate else None

exchange = {
    'cal_per_mile_run':  cal_mile_run,
    'cal_per_mile_ride': cal_mile_ride,
    # Miles of each sport that buy exactly one pint.
    'run_miles_per_pint':  round(BEER_CAL / cal_mile_run, 1)  if cal_mile_run  else None,
    'ride_miles_per_pint': round(BEER_CAL / cal_mile_ride, 1) if cal_mile_ride else None,
    'races': [
        {'name': '5K',        'pints': _pints(3.1,  cal_mile_run)},
        {'name': '10K',       'pints': _pints(6.2,  cal_mile_run)},
        {'name': 'Half',      'pints': _pints(13.1, cal_mile_run)},
        {'name': 'Marathon',  'pints': _pints(26.2, cal_mile_run)},
        {'name': 'Century',   'pints': _pints(100,  cal_mile_ride)},
    ],
}

beer_block = {
    'cal_per_pint':  BEER_CAL,
    'calories_ytd':  round(cal_ytd_all),
    'pints_ytd':     round(cal_ytd_all / BEER_CAL, 1),
    'calories_30d':  round(cal_30d),
    'pints_30d':     round(cal_30d / BEER_CAL, 1),
    'window_days':   30,
    'by_month':      months,
    'exchange':      exchange,
    # Pints burned per day over the rolling window — the figure the page
    # compares against actual drinking rate.
    'pints_per_day': round(cal_30d / 30 / BEER_CAL, 2),
}
print(f"Beers burned: {beer_block['pints_ytd']} pints YTD "
      f"({beer_block['calories_ytd']:,} cal @ {BEER_CAL}/pint), "
      f"{beer_block['pints_30d']} in last 30d")
print("  by month: " + " · ".join(f"{m['month']} {m['pints']}" for m in months))

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


# ── Badges ─────────────────────────────────────────────────────────────
# Garmin awards badges for milestones (first 5K, a distance total, a streak).
# get_earned_badges() returns every badge ever earned, which for a long-time
# user is hundreds of entries — so we keep only the ones earned recently and
# cap the list. The card is meant to say "look what just happened", not to be
# a trophy cabinet.
#
# Wrapped in its own try/except on purpose: the badge endpoint is not part of
# the documented API and could change or disappear without warning. If it
# breaks, training.json should still get written with everything else intact.
badges = []
try:
    earned = client.get_earned_badges() or []
    cutoff = datetime.now(timezone.utc) - timedelta(days=BADGE_WINDOW_DAYS)
    for b in earned:
        raw = b.get('badgeEarnedDate') or ''
        if not raw:
            continue
        # Garmin returns e.g. "2026-09-04T19:12:31.0" — tolerate variants
        try:
            when = datetime.fromisoformat(raw.replace('Z', '+00:00').split('.')[0])
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if when < cutoff:
            continue
        badges.append({
            'id':     b.get('badgeId'),
            'name':   (b.get('badgeName') or '').strip(),
            'date':   when.strftime('%Y-%m-%d'),
            'pretty': when.strftime('%b %d'),
            # how many times this badge has been earned, when Garmin tracks that
            'count':  b.get('badgeEarnedNumber') or 1,
        })
    badges.sort(key=lambda x: x['date'], reverse=True)
    badges = badges[:BADGE_MAX]
    print(f"  Badges: {len(badges)} earned in the last {BADGE_WINDOW_DAYS} days")
except Exception as e:
    # Keep whatever we had rather than blanking the card on a transient failure
    badges = cached.get('badges', [])
    print(f"  Badges: endpoint failed ({type(e).__name__}) — kept {len(badges)} cached")

output = {
    'source':                       'garmin',
    'updated':                      datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'ytd':                          ytd_block,
    'beers':                        beer_block,
    'all_time':                     alltime_block,
    'all_time_counted_through_id':   counted_through_id,
    'all_time_counted_through_date': cached.get('all_time_counted_through_date', ''),
    'activities':                   activities,
    'badges':                       badges,
}

os.makedirs('data', exist_ok=True)
with open('data/training.json', 'w') as f:
    json.dump(output, f, indent=2)

# Separate file, deliberately. FuelCast lives in another repo and fetches
# this over raw.githubusercontent; keeping it out of training.json means
# that consumer isn't downloading the whole dashboard payload, and the
# contract between the two repos stays small and obvious.
with open('data/training-load.json', 'w') as f:
    json.dump({
        'source':     'garmin',
        'updated':    datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'athlete':    'bdgroves',
        # Body composition, measured energy and recovery. Keys are only
        # present when their fetch succeeded, so consumers must treat each
        # as optional.
        **athlete_state,
        **tss_block,
    }, f, indent=2)
print(f"data/training-load.json written — {len(daily_tss)} days of TSS "
      f"({tss_block['start']} to {tss_block['end']})")

print(f"data/training.json written — {len(activities)} recent activities")
print(f"  YTD Run: {ytd_block['run']['miles']} mi · {ytd_block['run']['count']} runs")
print(f"  YTD Ride: {ytd_block['ride']['miles']} mi · {ytd_block['ride']['count']} rides")
print(f"  YTD Swim: {ytd_block['swim']['yards']} yd · {ytd_block['swim']['count']} swims")
print(f"  YTD Yoga: {ytd_block['yoga']['count']} sessions")
print(f"  YTD Strength: {ytd_block['strength']['count']} sessions")
print(f"  All-Time Run: {alltime_block['run']['miles']} mi · {alltime_block['run']['count']} activities")
print(f"  All-Time Ride: {alltime_block['ride']['miles']} mi · {alltime_block['ride']['count']} activities")
print(f"  All-Time Swim: {alltime_block['swim']['yards']} yd · {alltime_block['swim']['count']} activities")
