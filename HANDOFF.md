# HANDOFF: brooksgroves.com and the story sites

Read this at the start of a new chat. Last updated Oct 26, 2026. (This file is served publicly with the site, so it holds no passwords or private links.)
For the longer story of the redesign, see REDESIGN.md. For how the pages are built, see ARCHITECTURE.md.

---

## Where things stand

The redesign (direction A, "Refined almanac") is **done and live**. Every card, page and post has a picture in one house style.

- **Homepage**, in order:
  1. Featured carousel
  2. Start here
  3. Latest writing (4 picture cards)
  4. Six topic cards
  5. Live right now (Kīlauea, biggest quake, Rainier snowpack, Lake Tahoe level)
  6. The Work: 6 sections, 28 cards, every row full (Weather & Water, Volcanoes & Earth, Deep Time, Geospatial, Ecology, More)
  7. Publications
  8. Stories & Journeys
  9. Quote
- **New pages and features:**
  - /topics/ and six topic pages
  - /work/ and /live/ hubs
  - /search/ (Pagefind)
  - The six-door menu on every page, story sites included
  - Keep reading cards, link previews and WebP images
- **Outside:** jump cards with pictures, a 12-book Bookshelf that refreshes itself, football scores (built from ESPN's schedule feed, since the /teams/ endpoint is blocked from browsers), the Grand Tours and a Dakar 2027 card.
- **Games** (/games.html): five cards with pictures: Kellath's Drift, Offline Protocol, Adjuster's Report, Railroad Valley, Plate Hunter.
- **Maps:** dashboard cards are whole links, places-lived zoom fixed, Chiricahua National Park added (made a national park Oct 20, 2026).
- **Analytics:** Cloudflare Web Analytics is on and verified. The token is in `data/analytics.json`, and `scripts/analytics.py` adds the beacon to all pages. Automatic injection never worked, because the site is served by GitHub, not through Cloudflare.
- **Story sites:** all seven memoir collection cards have pictures, and the Westin, Y2K and Journal home pages have covers. The Plate Hunter post has its cover too.
- **Branches:** cleaned up. The website repo has `main` plus `link-report` (the link checker's output). secchi's `dotnet-stream` is work in progress, so leave it.

## Open items (pick from here)

1. **Write the first story** from the list. Suggested: *Hurricane Gilbert* (Blinn, Sept 1988).
   - The list (32 stories, all sorted by collection) is the Google Doc "Story Ideas" in Brooks's Drive, with the same list in `brooks-memoir/STORY-IDEAS.md`.
   - Tick off both when a story is published.
2. **Review analytics** in early November: what people click, then tune the homepage.
3. **QGIS:** stay on 4.2.2. Releases 4.2.3 and 3.44.15 are blocked by Smart App Control (QGIS issues #67751 and #67814, no fix yet). A weekly check was offered but not set up.
4. **Optional:**
   - Alt text for the hero pictures
   - A Lighthouse speed and accessibility pass
   - Restyling the five original heroes (PELE, STORM CHASER, Project Kiva, LiDAR Explore, HopLove)
   - A HOLDOVER prompt once that game is built
5. **Parked:** the Ruby Crest trail story (the blog post covers enough for now) and the secchi note to the Tahoe Institute and UNR alumni.

## How to add a picture (the routine)

1. Prompts use `docs/hero-image-prompt.md` (the house style). Filled-in sets are in `docs/hero-prompts-*.md`.
2. Save the image to `images/features/<name>.jpg`, or `blog/img/<post>/og.jpg` for a post.
   - **Use a new filename when replacing an image** (for example `-2`), so browsers don't show a cached old one.
3. Where to wire it:
   - **A post:** add it to `IMAGE_OVERRIDES` in `scripts/keep_reading.py`. That covers the cover, cards and link preview.
     - `og_tags.py` lets an override replace a topic stand-in, but keeps a post's own chosen `og:image`. If a post's own og:image is a screenshot, edit its meta tag directly.
   - **A homepage Work card:** make a 640×360 WebP in `images/thumbs/` and change the card's `src` in `index.html`.
   - **A dashboard on the topic or hub pages:** set `img` in `data/topics.json`. Edit only that value; never rewrite the whole file.
   - **A new card type with its own `<img>` class:** add the class to the `CARD` regex in `scripts/web_images.py`.
4. Run the generator chain from `scripts/`, in this order:
   `home_topics keep_reading topic_pages hub_pages site_nav og_tags post_polish analytics web_images`
5. Push, wait for "Deploy Jekyll…" to succeed, then check the live page.
   - "pages build and deployment: cancelled" is normal.
   - If the deploy fails with "in progress deployment", re-run the failed job.

## Gotchas learned the hard way

- **Pictures are 16:9 with the title top-left.** Any crop that isn't 16:9 cuts the title.
  - An `<img>` with `width`/`height` attributes also needs `height:auto` in its CSS, or the aspect-ratio is ignored.
  - Post covers trim from the bottom (`object-position: center top`).
- **In the page, calendar dates** ("2025-09-02") go through a formatter, never `new Date(...)`.
- **The sandbox can't reach most sites.** Check live pages with WebFetch or Brooks's built-in browser, when it's connected.
- **This session can't delete GitHub branches.** Brooks does it from PowerShell. Give him `git -C <folder> …` commands, so they work from any folder. A bare `cd` plus a command that fails can run in the wrong repo.
  - His website folder is `C:\Users\brook\Projects\bdgroves.github.io`.
  - He also has a secchi copy in WSL (`\\wsl.localhost\Ubuntu\home\brook\secchi`) besides `C:\Users\brook\Projects\secchi`.
- **Story sites** (memoir, westin, journal, y2k) are private repos behind Cloudflare Access. Don't feature them on the homepage, and never make them public.
- **Brooks's Windows laptop has Smart App Control.** New pixi envs, rasterio and QGIS updates get blocked. Heavy work goes to GitHub Actions or WSL. forge3d renders through the trusted humphreys-orbit env (the `f3d` function).
- **Blog voice is friendly and warm.** A separate agent fact-checks a post before it's published. Every new post gets a picture.
- **Commits end with:**
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
  `Claude-Session: https://claude.ai/code/session_01CyZ7bHtNLaRDxEz7KkKuAL`

## Where things live

| What | Where |
|---|---|
| Website | `bdgroves/bdgroves.github.io` (GitHub Pages, Jekyll via Actions) |
| Memoir, Westin, Journal, Y2K | `brooks-memoir`, `westin-stories`, `brooks-journal`, `y2k-journal` (Cloudflare Pages) |
| Redesign running log | The redesign Google Doc in Brooks's Drive (Roboto); search Drive for it |
| Story list | Google Doc "Story Ideas" in Brooks's Drive, and `brooks-memoir/STORY-IDEAS.md` |
| Picture prompts | `docs/hero-image-prompt.md`, `docs/hero-prompts-*.md`, `brooks-memoir/docs/picture-prompts.md` |
| secchi | `bdgroves/secchi`, with its own HANDOFF.md |
