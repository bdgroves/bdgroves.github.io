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
| 1 | Readability fixes in the shared stylesheet | ✅ on `redesign-a` |
| 2 | "Keep reading" cards at the end of every post | ✅ on `redesign-a` |
| 3a | Homepage images: featured carousel and image topic cards | ✅ on `redesign-a` |
| 3b | Homepage layout: six-door nav, Start-here paths, Live right now | next |
| 4 | Topic pages; Work, Maps & films, Live data pages | |
| 5 | Outside page; the Stories front door | |
| 6 | Shared header across brooksgroves.com and the subdomains | |
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

## Image wish list

Posts and projects with no usable image yet (33). Each needs a 1200×630
picture; when one lands, add it as the post's `og:image` (or to
`IMAGE_OVERRIDES` in `scripts/keep_reading.py`) and re-run the script.

- The Rock Eaters
- The Alert Bots, Revisited
- Where the Trail Runs Out (RIDGELINE)
- Six Islands, Six Lizards
- Where the Fog Lives (FOG-WATCH)
- FuelCast
- What Really Happened on Easter Island
- From a Pile of Bookmarks to a Searchable Cookbook
- Bob's Gang Wanted a Trade Journal
- Boo Before You're Ready
- I Wanted to Play Star Frontiers Again (games engine)
- Thirty Minutes, Fifty Years of Fire (its og:image points at
  `/images/tuolumne-watershed-map.png`, which doesn't exist: a broken social
  preview today)
- BdgrovesBot
- SOLSTICE post
- Sierra Nevada Alert Bot
- AFTERSHOCK post
- DIPODOMYS
- Little Free Pantry
- Weather Station
- FORTRAN, Snowpack, and the Language the Atmosphere Speaks
- Why I Switched to pixi
- Building a Live Streamflow Dashboard
- A Draught of the South Land (book review)
- Quantum Physics and Volcanology curricula
- Sports and Beer; Giro, Tour and Vuelta trackers

Done: **HopLove** (the "Look at a can. Know the hops." poster,
`images/features/hoplove.jpg` and `.webp`).
Done: **Project Kiva** ("Reading the ground with lasers") and **LiDAR Explore**
("From point clouds to forest intelligence"), from Brooks, Oct 20. LiDAR Explore
was added to the featured carousel (10 projects now).
Done: **PELE**, **Rainier Snowpack** (also the Weather & Water topic card) and
**SIERRA-FLOW** (cards for the COBOL and Handoff posts), from Brooks, Oct 20.

## Known issues to pick up

- `js/site-footer.js` embeds the whole shared CSS, now including the
  Keep-reading rules the footer doesn't need (~3 KB). Harmless; trim in
  `build_footer_js.py` if it matters.
- Some POSTS dates are "April 2026" or "2026" rather than ISO dates; cards
  show them as written.
