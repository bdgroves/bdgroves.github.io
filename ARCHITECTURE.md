# Site Architecture — Quick Reference

*Last updated: July 27, 2026. This doc exists so future-Brooks doesn't have to
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
  in real time during a live Tour. *Caveat: Wikipedia articles restructure
  heavily in the 48–72 hours after a Grand Tour finishes — captions get
  stripped, classifications get consolidated. See "Race results parser"
  below for how the workflow handles that.*
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
  marker. Numbers as of July 27, 2026: **19,280.5 mi running (4,683
  activities) · 15,386.7 mi cycling (1,003) · 135,681 yd swimming (88)**.
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
| TDF/Giro/Vuelta stuck as "live" after end date | Wikipedia article restructure or parser hiccup | See "Race results parser" below — Tier 2 insurance flip should self-heal within 3 days; manual patch to `cycling.json` is safe |
| Rider win-counts wrong | Race not marked `"final"`, or winner name doesn't match rider's last name | Check `cycling.json` winner field spelling |
| Garmin data stale | Token expired | See "Refreshing the Garmin token" below |
| All-Time looks wrong | Counted-through marker corrupted | Re-run `garmin_backfill_alltime.py` (safe, always recomputes clean) |
| Baseball/Football cards blank | ESPN/MLB API hiccup (client-side, no workflow) | Check browser console — nothing server-side to check |
| Workflow push fails repeatedly | Two workflows raced on a commit | Should self-heal via retry-with-rebase (3 attempts); beyond that, check for a real merge conflict |

## Refreshing the Garmin token

The `fetch-garmin.yml` workflow will fail loudly (non-zero exit, GitHub email)
when the saved token gets rejected — that's the signal to run this.
Observed cadence: **~11–15 days between rejections** based on three real
data points across July 2026. Not "6-18 months" as the script's SUCCESS
banner claims. Set an expectation of doing this roughly bi-weekly.

Runbook — about 90 seconds:

1. Confirm the failure — GitHub email will show "FATAL: token rejected" in the log
2. `cd C:\data\01_Projects\bdgroves.github.io`
3. `pixi run python garmin_login_setup.py` — enter email, password, MFA if enabled
4. Open `garmin_tokens_output\garmin_tokens.json`, copy the entire contents
5. GitHub → repo Settings → Secrets and variables → Actions → `GARMIN_TOKENS_JSON` → Update → paste → Save
6. Actions tab → Fetch Garmin Data → Run workflow → confirm "Token login OK" in the log
7. `Remove-Item -Recurse -Force garmin_tokens_output` (local scratch, don't leave it lying around)

The `garmin_tokens_output/` folder is gitignored, so accidentally committing
a token isn't a risk, but deleting it after each refresh keeps the working
directory clean and the GitHub Secret as the single source of truth.

## Race results parser (Grand Tours)

The `fetch-race-results.yml` workflow scrapes Wikipedia articles for the three
Grand Tours and writes to `data/{giro,tdf,vuelta}-2026.json` plus syncs the
final state into `cycling.json`. Runs twice daily at 17:00 and 22:00 UTC while
a race is in its active window (window_start-1 day to window_end+5 days).

### Two-tier "live" → "final" status transition

Wikipedia articles restructure heavily in the 48–72 hours after a Grand Tour
finishes. The parser has two fallback tiers so the sync can never leave
`cycling.json`'s row stuck as `live` past the race's actual end:

- **Tier 1 (full data):** `stages_done >= total-1` AND parsed GC exists AND
  `today > window_end` → set `status=final`, populate `winner` / `team`
  from `gc[0]`.
- **Tier 2 (insurance flip):** `today > window_end + 3 days` AND status is
  still `live` → flip `status='final'` regardless of GC. Better to display
  "Final" with no winner name than "Live" a week after the race ended.

The sync step runs unconditionally at the end of every workflow run — even
for races past the active parsing window — so Tier 2 fires without depending
on the parser succeeding.

### What the parser handles about post-race Wikipedia

Once a Grand Tour ends, Wikipedia editors typically do one or more of:

1. **Strip captions** from classification tables. Mid-race a caption reads
   "General classification after Stage 10"; post-race the same table is
   often uncaptioned and identified only by its section heading.
2. **Rename headings** ("Mountains classification" ↔ "King of the mountains",
   "Young rider classification" ↔ "Best young rider").
3. **Restructure the entire "Classification standings" section** into a
   "Final standings" section or split it across sub-articles.

The parser tries two passes in sequence:

- **Pass 1 (caption-based):** matches "General classification after Stage N"
  and similar. Only fires while the race is still running.
- **Pass 1b (heading-based fallback):** scans H2/H3 headings for "General
  classification", "Points classification", "Mountains classification" /
  "King of the mountains", "Young rider classification" / "Best young rider".
  Uses a sentinel stage marker (999) so post-race data always overrides any
  in-race snapshot Pass 1 might have picked up.

### Known quirks — not bugs, just Wikipedia data quirks

- **Team time trials have no rider winner.** If Stage 1 of a Grand Tour is
  a TTT (as it was for the 2026 TDF), Wikipedia's Stage characteristics
  table leaves the Winner cell empty because the "winner" is a team, not
  a rider. The parser silently skips it and extracts 20 of 21 stages. This
  is why Tier 1's threshold is `stages_done >= total-1` and not
  `>= total` — one missing TTT stage is expected and shouldn't block the
  status transition. If a TTT winner team is needed for the standalone
  tracker page, fill it by hand in `data/{race}-2026.json`.
- **Empty winner cells during the race.** Individual stages sometimes
  appear in the Stage characteristics table before the winner cell is
  populated. Self-heals on the next run — nothing to do.

### If it stalls anyway

Check the workflow log for two key lines:

```
[parse] N stage winners extracted           ← should be >= total-1
[sync] tdf: leader=..., stages_done=N, status=...   ← target: status=final
```

If Tier 1 didn't fire and Tier 2 hasn't fired yet (< 3 days past end), a
manual patch to `cycling.json` is completely safe: set `status="final"`,
`winner="<Name>"`, `team="<Team>"`. `fetch-cycling.yml` explicitly preserves
cached Grand Tour rows (see "Why things are built this way" above), and the
race-results workflow will happily agree with the manual values on its next
run rather than overwriting them.

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
