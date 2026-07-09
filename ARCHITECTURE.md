# Site Architecture — Quick Reference

*Last updated: July 9, 2026. This doc exists so future-Brooks doesn't have to
reverse-engineer past-Brooks's reasoning. If something on the site breaks or
looks weird, start here before diving into code.*

## Automated workflows (`.github/workflows/`)

| Workflow | Runs | Does | Never touches |
|---|---|---|---|
| `fetch-race-results.yml` | 17:00 + 22:00 UTC | Wikipedia → GC, stage winners, jerseys for Giro/TDF/Vuelta → `data/{race}-2026.json` + syncs into `cycling.json` | one-day races |
| `fetch-cycling.yml` | 20:00 UTC | PCS/calendar → one-day race results + rider win-counts (computed from calendar, not scraped) | Grand Tour rows in `cycling.json` (explicitly preserved — see below) |
| `fetch-cycling-news.yml` | every 6h | RSS → `data/cycling-news.json` | — |
| `fetch-garmin.yml` | 08:00 UTC daily | Garmin Connect (via pixi + `scripts/fetch_garmin.py`) → `data/training.json`: YTD, incremental all-time, recent activities w/ HR + calories | — |
| `fetch-strava.yml` | **disabled** | Retired — kept as a paper trail | — |

**Baseball & Football are NOT workflows.** They're client-side JS in
`outside.html` calling MLB Stats API / ESPN's `site.api.espn.com` live on
every page load — no server-side data file, nothing to check but the browser
console.

## Why things are built this way

- **Wikipedia owns Grand Tour data, not PCS.** PCS's live-race GC page URL
  changes mid-race and its rider-stats page class names break without
  notice. Wikipedia's GC/stage-winner tables are stable and crowd-maintained
  in real time during a live Tour.
- **`fetch-cycling.yml` explicitly guards `category == "Grand Tour"`** and
  preserves cached GT fields from `cycling.json` every run. Without this,
  PCS's stale scrape would silently clobber Wikipedia's correct data. Look
  for `"Preserved cached GT: ..."` in the log to confirm the guard fired.
- **Rider win-counts come from the calendar, not PCS scraping.** PCS removed
  the `table.rdrResults` class this session. Wins are now derived by
  matching calendar race winners against tracked riders — self-consistent:
  if it's shown as a win on the dashboard, it counts.
- **Garmin uses a saved token file, not username+password, in CI.** A
  password in a GitHub Secret is full account access if it ever leaks. The
  real password is typed in exactly one place —
  `garmin_login_setup.py`, run locally, never in CI.
- **All-time totals are incremental, not recomputed daily.** Garmin has no
  single "lifetime totals" endpoint like Strava did.
  `garmin_backfill_alltime.py` pages through full history ONCE, stores a
  true baseline + the newest activity ID seen (`all_time_counted_through_id`
  in `training.json`). Each daily run only adds what's newer than that
  marker. Real backfilled numbers as of July 9, 2026: **19,219.2 mi
  running (4,659 activities) · 15,386.7 mi cycling (1,003) · 135,681 yd
  swimming (88)**.
- **Strava was replaced, not fixed.** Their Developer Program went
  subscriber-only for API access June 30, 2026 — a policy change, not a
  bug. `fetch-strava.yml` is disabled but left in the repo in case that
  ever reverses.
- **Performance/Readiness cards (race predictions, VO2 max, training
  readiness, HRV, body battery) were built, then removed on purpose.** They
  worked, but added clutter that didn't earn its place. Don't rebuild
  without re-litigating whether it's actually wanted this time.

## Secrets & local-only files

| What | Where | If it breaks |
|---|---|---|
| `GARMIN_TOKENS_JSON` | GitHub → Settings → Secrets → Actions | Re-run `garmin_login_setup.py` locally, paste the new token file contents in as the secret value |
| `STRAVA_*` (3 secrets) | GitHub Secrets | Unused, workflow disabled — irrelevant unless Strava un-paywalls |
| `garmin_tokens_output/` | Local only, gitignored | Temp folder from login/backfill scripts — safe to delete after each use |

## Troubleshooting quick-hits

| Symptom | Likely cause | Fix |
|---|---|---|
| TDF/Giro/Vuelta stuck | Wikipedia article structure changed | Check `fetch-race-results.yml` log for `"[parse] found N wikitables"` — 0 means the article changed, re-inspect it |
| Rider win-counts wrong | Race not marked `"final"`, or winner name doesn't match rider's last name | Check `cycling.json` winner field spelling |
| Garmin data stale | Token expired | Re-run `garmin_login_setup.py`, update `GARMIN_TOKENS_JSON` |
| All-Time looks wrong | Counted-through marker corrupted | Re-run `garmin_backfill_alltime.py` (safe, always recomputes clean) |
| Baseball/Football cards blank | ESPN/MLB API hiccup (client-side, no workflow) | Check browser console — nothing server-side to check |
| Workflow push fails repeatedly | Two workflows raced on a commit | Should self-heal via retry-with-rebase (3 attempts); beyond that, check for a real merge conflict |

## Repo notes

- **pixi** (`pixi.toml` / `pixi.lock`) currently only runs `fetch-garmin.yml`.
  The other three workflows still use plain `pip install` — never migrated,
  no strong reason to unless consistency matters more later. Windows
  gotcha: pixi tasks need `python`, not `python3` — no `python3.exe` alias
  exists in a pixi env on Windows.
- **`scripts/fetch_garmin.py`** is the real Garmin logic, pulled out of
  inline YAML specifically so pixi could run it as a named task
  (`pixi run fetch-garmin`).
- **`garmin_login_setup.py`** and **`garmin_backfill_alltime.py`** are
  one-time LOCAL scripts. Never run in CI, never touch GitHub directly.
