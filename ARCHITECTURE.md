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

# Cloudflare Workers

Two Workers currently in production, both under the free tier. Both
were built by Brooks; both power live features on brooksgroves.com. If
either goes down, the corresponding features on the site stop working.

Neither has a Custom Domain attached — they run on `.workers.dev` URLs.
That means the URLs appear directly in the site's HTML source (someone
viewing page source can see them). Traffic is low (~20 requests/day
total across both), so hardening beyond current CORS restrictions
hasn't been necessary yet.

## brooks-anthropic-proxy

**URL:** `brooks-anthropic-proxy.bdgroves1970.workers.dev`

**Purpose:** Backs the recipe management system + the "Nora Reader" +
"Recipe Extractor" tools. Handles four routes:

| Method / Path | What it does |
|---|---|
| `POST /` | Forwards request body to Anthropic Messages API (used by Nora Reader + Recipe Extractor) |
| `POST /save-recipe` | Appends a recipe to `recipes.json` in this repo via the GitHub API, auto-commits with message `feat: add <title>` |
| `POST /delete-recipe` | Removes a recipe from `recipes.json`, auto-commits `chore: remove <title>` |
| `POST /update-recipe` | Edits an existing recipe in `recipes.json`, auto-commits `chore: edit <title>` |

**Secrets stored in the Worker:**
- `ANTHROPIC_API_KEY` — for the Claude API calls
- `GITHUB_TOKEN` — fine-grained PAT with Contents R+W on this repo

**CORS:** properly restricted. `DEFAULT_ORIGINS` in the code allows only:
- `https://brooksgroves.com`
- `https://bdgroves.github.io`
- `http://localhost:8000` (for local dev)
- `http://127.0.0.1:8000`

Overridable via the `ALLOWED_ORIGINS` env var.

**Key files that depend on this Worker:**
- Whatever pages implement the recipe UI + Nora Reader (grep the repo
  for `brooks-anthropic-proxy` to find current callers)
- `recipes.json` at the repo root — the data file this Worker writes to

**Deploy method:** Manual via the Cloudflare dashboard. No Git
integration — code is edited/uploaded directly in the Cloudflare
editor. Source lives inside Cloudflare only, not in this repo.

## tiny-dawn-75f1

**URL:** `tiny-dawn-75f1.bdgroves1970.workers.dev`

**Purpose:** Utility Worker that does TWO different jobs on the same
domain. Kept the auto-generated Cloudflare name to avoid breaking
callers — it's fine, just don't be surprised by it.

| Method / Path | What it does |
|---|---|
| `POST /` | AI tutor for learning curricula (desert, ecogeo, volcanology, reggae, quantum-physics). Accepts two request formats — new `{system, messages}` and legacy `{question, lesson}` — and forwards to Anthropic Messages API. Model: `claude-sonnet-4-5`, max_tokens 800. |
| `GET /proxy?url=...` | Generic CORS proxy — fetches the target URL server-side and returns the HTML, letting front-end JS pull cross-origin content that would otherwise be blocked. |

**Secrets stored in the Worker:**
- `ANTHROPIC_API_KEY` — for the Claude API calls

**Known callers:**
- `index.html` (line 673) — reggae music tutor Q&A widget
- `outside.html` (line 1390) — Peaks and Pints beer taplist scraper
  (fetches `peaksandpints.com/on-tap/` and parses for specific breweries)
- Learning pages at `brooksgroves.com/learning/*` — desert, ecogeo,
  volcanology, quantum-physics curricula. Each uses a curriculum-specific
  system prompt.

**CORS:** OPEN — `Access-Control-Allow-Origin: *`. Anyone from any
website can call this Worker. Low risk given low traffic, but if you
ever see requests spike unexpectedly, this is the first thing to
tighten (change the `*` to an allowlist like `brooks-anthropic-proxy`
uses).

**Deploy method:** Same as brooks-anthropic-proxy — manual, Cloudflare
dashboard only, no Git.

## Runbooks

### Someone's using the reggae tutor / recipe manager and it broke

1. Cloudflare dashboard → **Compute → Workers & Pages**
2. Click the relevant Worker (`tiny-dawn-75f1` for tutors, `brooks-anthropic-proxy` for recipes)
3. Check the **Metrics** tab for errors
4. Check the **Deployments** tab — is the latest version the one you expect?
5. Common cause: Anthropic API key expired or rate-limited. Rotate at
   [console.anthropic.com](https://console.anthropic.com), update the
   Worker's `ANTHROPIC_API_KEY` secret.

### Change what a Worker does

1. Cloudflare dashboard → **Compute → Workers & Pages** → click the Worker
2. Look for **"Edit code"** button (top of overview page)
3. Modify the JS in Cloudflare's inline editor
4. **Save and Deploy** — takes effect immediately

Note: there's no Git backup of these Workers. If you make a bad edit,
you can roll back via the **Deployments** tab (older versions listed
there can be restored).

### Rotate the Anthropic API key

Both Workers use the same `ANTHROPIC_API_KEY` (they're independent
secret bindings, but happen to point at the same underlying key). To
rotate:

1. [console.anthropic.com](https://console.anthropic.com) → API Keys →
   generate new key
2. Cloudflare → **brooks-anthropic-proxy → Settings → Variables and
   secrets** → click `ANTHROPIC_API_KEY` → update with new value → save
3. Repeat for `tiny-dawn-75f1`
4. **Test both**: hit the reggae tutor and the recipe manager, verify
   they still work
5. Revoke the old key on Anthropic's site

### Tighten CORS on tiny-dawn-75f1

If you ever want to lock it down like `brooks-anthropic-proxy`:

1. Edit the Worker code
2. Replace `'Access-Control-Allow-Origin': '*'` with an origin-check
   pattern (borrow the `DEFAULT_ORIGINS` + `buildCorsHeaders` pattern
   from `brooks-anthropic-proxy` — it's clean, tested, and already
   living in this account)
3. Save + deploy
4. Test each site that calls the Worker to confirm it still works

## History

- **2026-05 (approx):** Both Workers built as part of learning
  experiments. Names left as Cloudflare auto-generated defaults
  (`tiny-dawn-75f1`, later a `bitter-bush-83f0` that turned out to be
  an unmodified Hello World template).
- **2026-08-10:** Audit + cleanup. Deleted `bitter-bush-83f0` (unused
  Hello World). Kept both real Workers. Documented what each does.
  Decision: don't rename `tiny-dawn-75f1` — the URL is embedded in
  multiple HTML files across brooksgroves.com and the learning site,
  and renaming would require a coordinated multi-file update. Docs are
  a better investment than a rename.
