# Redesign A: "Refined almanac"

*Started October 20, 2026. This is the map for the site-wide redesign: what we
chose, why, what's done, and what's next. If a session gets lost, start here.
Brooks keeps a running log in the Google Doc "brooksgroves.com Redesign A:
running log" in his Drive.*

## The goal

More traffic and clicks, and an easier way into the content that matters to
each visitor, in a modern design that still looks like this site.

## What we chose, and why

Direction **A, "Refined almanac"**, out of three mocked up (A refined, B field
journal, C atlas). It keeps the brand: parchment, ink, Playfair Display, DM Mono
labels and Libre Baskerville, with emojis **inline** as they are today. No big
emoji tiles.

- Plain mono nav with six doors: **Work · Writing · Maps & films · Live data ·
  Outside · About**, plus a quiet **Stories** door (see below).
- A rotating featured-project carousel using **real project images** (e.g. the
  secchi banner, the HopLove poster). Every project also appears on a topic page
  or the Work page, so nothing depends on the carousel.
- Topic cards with an image, the inline emoji, the newest posts and a count.
- Image-led cards everywhere; every post and project gets a 1200×630 image.

Mockups live in the "brooksgroves.com redesign options" design canvas
(claude.ai artifact). The design system is the "brooksgroves.com" Design System
artifact. Both are private to Brooks.

### Trade-offs we accepted

- A relies on images: anything without one looks unfinished. See the image
  wish list below.
- It's calmer than today's dense newspaper homepage; the weather bar's charm
  moves into a "Live right now" panel.
- Carousels hide slides 2–9 from most visitors, hence the rule above.

## Journal, memoir, Y2K, Westin

These stay password-gated and out of search, and **are not featured on the
homepage**. They share the house look through the shared footer and (later) a
shared header. On the main site they get one warm "Stories" front door: a card
per collection with a one-line description and a 🔒 invite-only badge, no
excerpts. Memoir and journal get a reading mode; Y2K keeps its retro look
inside the shared frame.

## Rollout

Each step goes on a branch, is checked with screenshots and the contrast audit,
then merges.

| # | Step | Status |
|---|---|---|
| 1 | Readability fixes in the shared stylesheet | ✅ live Oct 20 |
| 2 | "Keep reading" cards at the end of every post | ✅ live Oct 20 |
| 3a | Homepage images: featured carousel and image topic cards | ✅ live Oct 20 |
| 3b | Homepage layout: six-door nav, Start-here paths, Live right now | ✅ live Oct 20 |
| 4 | Topic pages (/topics/), /work/ and /live/ | ✅ live Oct 20 |
| 5 | Outside page; the Stories front door | |
| 6 | Shared header across brooksgroves.com and the subdomains | main site ✅ live Oct 20; journal, memoir, Y2K, Westin live Oct 20 |
| — | og:image on every post (social previews, search) | ongoing, needs images |
| — | RSS feed | |

### Step 1: readability (done)

`css/site-footer.css` is already the shared stylesheet: every page links it,
and five repos use it (the subdomains too, via `js/site-footer.js`). The fix is
there, not in 116 pages:

- `html:root { --stone: #6b645a; --gold: #8a6418; }` — same hues, darker.
  Stone goes from 4.2:1 to 5.2:1 on parchment, gold from 2.4:1 to 4.7:1.
- Dark surfaces inside the light theme (footer, nav dropdowns, mobile menu,
  weather bar, code blocks) get the brighter pair back locally.
- Footer labels were `#3a3a36` on ink (1.5:1); now `#9a9183`.
- Tags-page dates were set in `--mist`, a border colour; now `--stone`.
- Dark mode: the weather bar stays dark.

**Measured** with a Playwright audit of all 116 pages (every text element,
its real background, WCAG AA): light mode went from **12,304** failing
elements to **677**; dark mode from **2,348** to about **1,500**. What's left is
page-specific colours (concert/race pages using `--mist` as text, page accents
like `#c0392b` in dark mode). Those get fixed as each page is redesigned.

Remember `python3 scripts/build_footer_js.py` after editing the CSS.

### Step 2: Keep reading (done)

`scripts/keep_reading.py` writes three related posts as image cards above the
footer of every post (69 posts), between `KEEP-READING` markers, plus a
"More in <topic> →" link to `tags.html#topic=<id>`.

- Same topic first (topics from `data/topics.json`, the same assignment the
  homepage cards use), most shared tags, newest breaking ties; then the newest
  posts to fill to three.
- Card image: `IMAGE_OVERRIDES` in the script, else the post's og:image, else
  its first content image (a local path must exist), else an emoji card in the
  topic colour.
- Gated subdomains are excluded, as on the homepage.
- Re-running is a no-op; the Home topics workflow runs it after
  `home_topics.py`, so adding a post to `tags.html` is still all it takes.
- Styles: "KEEP READING" section of `css/site-footer.css`.

### Step 3a: homepage images (done)

- The featured project is now a carousel: image on the left (on top on a
  phone), text on the right, ←/→ buttons, a bar per project, a pause
  button. It starts on a random project, rotates every 8 s, pauses while the
  mouse or keyboard focus is on it, and never auto-rotates for visitors who
  ask for reduced motion. Each `FEATURED` entry in `index.html` has `img` and
  `alt`; an empty `img` shows the project's emoji instead (FOG-WATCH today).
- Topic cards are image cards. Each topic in `data/topics.json` has an `img`;
  `scripts/home_topics.py` writes it into the card.
- Images live in `images/features/` (1200 px wide for projects, 800×350 for
  topics), cut from images already in the posts.

### Step 3b: menu, Start here, Live right now (live Oct 20)

- **Menu:** six doors (Work, Writing, Maps & films, Live data, Outside,
  About). Each label is a link to its landing (`/#work`, `/writing/`,
  `/maps.html`, `/#live`, `/outside.html`, `/about.html`) and opens a
  dropdown on hover or keyboard focus. Nothing from the old seven
  dropdowns was dropped; it was regrouped. The phone drawer uses the
  same six doors. Only the homepage has the new menu so far; the other
  pages get it with the shared header (step 6).
- **Start here:** three cards under the carousel (maps and data; outdoors
  and nature; stories), four hand-picked links each. Edit the list in
  `index.html` (search for `START HERE`).
- **Live right now:** three tiles read live data in the browser:
  Kīlauea from `/PELE/data/volcanoes.json` + `episodes.json`, the biggest
  M2.5+ quake of the last day from the USGS feed AFTERSHOCK uses, and
  Rainier from `/rainier-snowpack/data/processed/snotel_latest.json`. A
  tile that can't load says so and still links to its dashboard.

### Step 4: topic pages (live Oct 20)

`scripts/topic_pages.py` writes `/topics/` and `/topics/<id>/` from
`tags.html` and `data/topics.json` (each topic now lists its
`dashboards`: name, url, img, blurb). Each page: hero image and blurb,
live dashboards as image cards, every post with its picture and a tag
filter (tool tags like Python are skipped; `#tag=Wildfire` links work),
and the other topics. Homepage topic cards and Keep reading's "More in"
link here now. Runs in the Home topics workflow.

### Step 6 (main site): the same menu on every page (live Oct 20)

`scripts/site_nav.py` puts the six doors in the header of 105 pages,
marks the current door, and keeps each page's theme button. Left alone:
the homepage (its own menu with dropdowns), the topic pages (same links,
their own header), the games, 404, and four pages with their own
designs (FuelCast, Sports, Recipes, the recipe extractor). Styles:
"SITE MENU" in `css/site-footer.css`. Runs in the Home topics workflow.

A note on the contrast audit: dark-mode counts include colours caught
mid-transition (pages animate colour for 0.15–0.2 s). Re-measured after
600 ms, the blog index, tags page and secchi post have zero dark-mode
failures. Use a longer settle time for dark-mode numbers.

### Step 6 (story sites): journal, memoir, Y2K, Westin

Same script, run from this repo against each clone:
`python3 scripts/site_nav.py --other-site ../brooks-memoir`. Links are
absolute (https://brooksgroves.com/...), Writing is the current door, and
each page's own "← Memoir"-style back link is kept. Two pages were done
by hand: the journal's bridge-of-promise.html (its own nav markup) and
Westin's index (its header had a "← brooksgroves.com" link, replaced by
the menu). Gates and noindex are untouched. Each repo has a `site-menu`
branch; merge after Brooks checks behind the password.

### Outside page (on `redesign-d`)

Four jump cards under the intro (My Season, The Teams, Pro Cycling, The
Taproom; the race card shows the live countdown), a sticky section bar,
emoji in the zone headings, dates and small labels in readable
`--stone` instead of `--mist`, and finished Grand Tours no longer fade
the whole card. Every id the live-data scripts use is unchanged. On a
phone the jump cards hide and the sticky bar does the job.

### Homepage topic cards moved up (live Oct 20)

The six topic cards were live but sat far down the page in the Writing
column, under "Stories & Journeys", where Brooks didn't see them. They
now have their own full-width **Topics** section right after Start here
(order: Featured → Start here → Topics → Live right now → The Work …).
`home_topics.py` writes two blocks: the cards between `TOPICS` markers
and the "Latest" post between `LATEST` markers (still in the Writing
column).

### Posts: cover, reading type, progress, contents (live Oct 20)

`scripts/post_polish.py` puts each post's own picture as a wide cover
above the article (skipped if the same picture already opens it; 38 of
68 posts get one) and adds `js/post.js`: a thin reading-progress bar and
a Contents list for posts with four or more sections (open on desktop,
folded on phones). Headline and body type are a little larger and
balanced. Styles: "POSTS" in `css/site-footer.css`.

### Work and Live data pages (live Oct 20)

`scripts/hub_pages.py` builds `/work/` (the 10 featured projects from the
homepage `FEATURED` list, with images and stack, then the eight fields)
and `/live/` (the three live readings, then all 24 dashboards and tools
from `data/topics.json`, grouped by topic, weather first). The Work and
Live data doors now open these pages on every site, including the story
sites.

### Finishing touches (on `redesign-g`)

- **Dark mode**: text set in `--mist` (a border colour) is now `--stone`
  on the race, Dakar, concert, tags, quotes and learning pages; page
  accent variables (--lava, --storm, --deep, --forest …) get brighter
  dark-mode values in `css/site-footer.css`. Audit (600 ms settle): dark
  failures 1,334 → 573, light 640 → 448.
- **Menus**: Recipes and the Recipe Extractor get the six doors.
  FuelCast's page is a sign-in screen and Sports redirects to Outside, so
  both are left as they are.
- **Stories & Journeys** on the homepage is one quiet line linking to the
  Writing page (the full front door), instead of six cards.
- **Latest writing** moved up: the four newest posts as image cards, right
  after Start here (written by `home_topics.py` between LATEST markers).
  The old Writing column at the bottom is gone; the **quote of the day**
  is now a quiet sign-off just above the footer.
- **Outside** gets a fifth jump card, 📚 The Bookshelf.
- **Analytics**: Brooks enabled Cloudflare's automatic injection for
  brooksgroves.com, so the token is not needed. `scripts/analytics.py`
  (Cloudflare Web Analytics, adds the beacon to every public page once
  `data/analytics.json` has a site token) is the fallback; `scripts/analytics.py` adds Cloudflare Web Analytics to
  every public page once `data/analytics.json` has the site token. Empty
  token = off.

## Image wish list

**Every new post gets a picture** (standing rule from Oct 20). Make it with
the house-style prompt in `docs/hero-image-prompt.md`.

Pages that still show an emoji on their cards (16, Oct 20). Any 1200×630
picture works; add it as the post's og:image or to `IMAGE_OVERRIDES` in
`scripts/keep_reading.py`, and every card, cover and preview picks it up.

Older posts:
- Thirty Minutes, Fifty Years of Fire (Tuolumne watershed)
- BdgrovesBot
- Sierra Nevada Alert Bot
- DIPODOMYS
- Little Free Pantry
- From a Pile of Bookmarks to a Searchable Cookbook
- Bob's Gang Wanted a Trade Journal
- Boo Before You're Ready
- Why I Switched to pixi

Other pages:
- A Draught of the South Land (book review)
- Quantum Physics and Volcanology curricula
- Sports and Beer; Giro, Tour and Vuelta trackers

Done with Brooks's images: RIDGELINE, Six Islands, Rapa Nui (Easter Island), The Alert Bots, Four Games One Engine, FuelCast (batch 1, from `docs/hero-prompts-batch-1.md`), The Rock Eaters, HopLove, Project Kiva, LiDAR Explore, PELE,
Rainier Snowpack, SIERRA-FLOW, FOG-WATCH, AFTERSHOCK, Sierra Streamflow,
PUGET-TIDES. Reusing pictures already on the site: SOLSTICE, Weather
Station and CASCADIA-WX first posts (from their "Revisited" posts).

### Homepage The Work + Publications, Bookshelf, search, faster images (live Oct 20)

- **The Work**: all 18 project cards are image cards (WebP thumbnails in
  `images/thumbs/`). **Selected Publications** is a card.
- **Reading** left the homepage for **The Bookshelf** on the Outside page
  (bigger Goodreads covers; same `/books.json`).
- **Search**: `/search/` (Pagefind). The index is built in the Pages
  deploy workflow, not committed; every menu has "⌕ Search".
- **Faster images**: `scripts/web_images.py` (runs last) serves WebP
  copies from `img-opt/` with srcset; originals stay for link previews.

## Known issues to pick up

- `js/site-footer.js` embeds the whole shared CSS, now including the
  Keep-reading rules the footer doesn't need (~3 KB). Harmless; trim in
  `build_footer_js.py` if it matters.
- Some POSTS dates are "April 2026" or "2026" rather than ISO dates; cards
  show them as written.

### Oct 20 — football scores fixed
ESPN stopped letting browsers call `site.api.espn.com/.../teams/{id}` (CORS), so the three football cards on Outside showed "Data unavailable". `loadFootball()` now builds each card from the `teams/{id}/schedule` feed, which is still open and carries the record, standing and logo. Checked live: Seahawks 3-3, UW 4-3, Nevada 2-4, with last and next games.

### Oct 20 — batch 2 pictures wired in
All 15 batch-2 pictures are in. Nine posts (Tuolumne watershed, BdgrovesBot, Sierra alert bot, DIPODOMYS, Little Free Pantry, cookbook, investment club, Halloween in August, pixi) now have their own picture on the cover, on cards and in link previews, replacing the topic stand-ins. The Giro, Tour and Vuelta pages have their pictures behind the page header, and so do their cards on Outside. Quantum physics, volcanology and the Draught of the South Land review each have a cover picture. All six of those pages now have link-preview pictures too.
`og_tags.py` now lets an IMAGE_OVERRIDES picture replace a topic stand-in. A post's own chosen og:image is still kept.

### Oct 21 — redesign wrapped
Done today: The Work rebuilt into six full sections (28 cards); house-style pictures for every Work card, the carousel, the six topic cards, the Outside jump cards and the homepage share picture (prompts in docs/hero-prompts-*.md); pictures shown whole at 16:9 on topic cards, topic pages and post thumbnails; Maps page fixes (clickable dashboard cards, places-lived zoom, Chiricahua National Park); a Lake Tahoe level tile; a new post (Wherobots).
Still open: alt text for the hero pictures; a Lighthouse speed/accessibility pass; optional restyle of the five original heroes (PELE, STORM CHASER, Project Kiva, LiDAR Explore, HopLove); Brooks's branch clean-up and the Cloudflare analytics check.
