# Private sites — Cloudflare Pages + Access

Deployment and access architecture for the four private subdomains:
`memoir`, `westin`, `journal`, `y2k`. Set up 2026-08-10; extends but
does not replace `ARCHITECTURE.md` (which covers the public
`brooksgroves.com` site).

## What's private, what's public

| Site | Domain | Status |
|---|---|---|
| Main site | brooksgroves.com | Public — GitHub Pages from `bdgroves/bdgroves.github.io` |
| Memoir | memoir.brooksgroves.com | Private — Cloudflare Pages + Access |
| Westin stories | westin.brooksgroves.com | Private — Cloudflare Pages + Access |
| Journal | journal.brooksgroves.com | Private — Cloudflare Pages + Access |
| Y2K journal | y2k.brooksgroves.com | Private — Cloudflare Pages + Access |

Public stays as-is (Jekyll build via GitHub Actions, DNS on Cloudflare
pointing at GitHub Pages). Everything else is on the new stack.

## The stack for private sites

Each of the four private sites uses the identical pattern:

```
GitHub (private repo, main branch)
   │
   │  push webhook
   ▼
Cloudflare Pages (auto-deploys on push)
   │
   │  serves via
   ▼
<sub>.brooksgroves.com  ←── Cloudflare Access gate
                              (email allowlist, One-time PIN)
                              ↑
                              custom dark login page
                              (bdgroves.cloudflareaccess.com)
```

**Why not GitHub Pages anymore:** GitHub Pages can serve private repos
only on the paid GitHub Pro tier. Cloudflare Pages does it free, so
the four private repos moved off GitHub Pages entirely.

**Why not Netlify:** Old orphaned Netlify deployments used to exist for
some of these repos. Removed 2026-08-10 to eliminate parallel public
URLs of otherwise-private content.

## Access — one shared allowlist, four sites

There is **one Cloudflare Access policy** named `Allowed emails`
(policy ID `c4747022-8f2b-4dfa-9d90-d09440cfab8a`) shared across all
four applications. Adding an email to that policy grants access to
every private subdomain.

Current allowlist (as of 2026-08-10):
- `bdgroves1970@gmail.com` (primary)
- `brooks.groves@outlook.com` (secondary — same person, backup)

Sessions last 24 hours. After that, users re-authenticate by
requesting another one-time code.

## Login flow

1. Visitor hits any of the four subdomains
2. Cloudflare Access intercepts before the site content loads
3. Shows the custom dark login page (styled to match memoir aesthetic:
   ink background `#1c1a16`, cream text `#ede8dc`)
4. Visitor enters their email
5. If email is on the allowlist → Cloudflare emails a 6-digit code
6. Visitor enters the code → gets a 24-hour session cookie
7. Site loads normally

If email is not on the allowlist → the code is never sent, silent deny.

## Individual page-level gates

Some HTML files inside the memoir and westin repos have their own
in-page JavaScript password prompts (from earlier work — commits
mention `memoir_auth`, `westin_auth`, `y2k_auth`, and `journal_auth`).
These are a **second layer** on top of Cloudflare Access, gating
specific pages that are more sensitive than the rest.

Effectively:
- Cloudflare Access = "you're on the allowlist"
- In-page password = "you know this specific memory's key"

Not all pages have the second gate. It's a per-page decision.

## Runbooks

### Add a person to the allowlist

They can now access ALL four private sites within seconds. Same for removal.

1. dash.cloudflare.com → **Zero Trust** (under Protect & connect)
2. **Access controls → Policies**
3. Click **Allowed emails**
4. Under **Include** → **Emails** → add their email → **Save**

### Remove a person

Same path. Click the ✕ next to their email chip → Save. Any active
session they have may still work for up to a few minutes, then locks
out.

### Deploy a change to any private site

```powershell
cd C:\data\01_Projects\<repo-name>
# edit files
git add .
git commit -m "…"
git push
```

Cloudflare Pages picks up the push within ~30 seconds and deploys.
Watch: dash.cloudflare.com → **Workers & Pages → <project> →
Deployments**.

### Change the custom login page appearance

1. Zero Trust → **Reusable components → Custom pages**
2. Under **Access login page**, click the existing custom page
3. Edit colors, header text, footer, logo
4. Save (applies immediately to all four apps)

### Add a new private site

Follow `cloudflare-cutover-checklist.md` — same pattern used for all
four here.

## Local repo paths

All private repos live under `C:\data\01_Projects\` on Brooks's
Windows machine, cloned via SSH:

```
C:\data\01_Projects\
├── bdgroves.github.io   (public — main site)
├── brooks-memoir        (private)
├── westin-stories       (private)
├── brooks-journal       (private)
└── y2k-journal          (private)
```

SSH clone URL pattern: `git@github.com:bdgroves/<repo>.git`

## Cloudflare project names

Matched to repo names for clarity:

| Cloudflare Pages project | GitHub repo | Custom domain |
|---|---|---|
| `brooks-memoir` | `bdgroves/brooks-memoir` | memoir.brooksgroves.com |
| `westin-stories` | `bdgroves/westin-stories` | westin.brooksgroves.com |
| `brooks-journal` | `bdgroves/brooks-journal` | journal.brooksgroves.com |
| `y2k-journal` | `bdgroves/y2k-journal` | y2k.brooksgroves.com |

## Troubleshooting

### "I pushed a change but Cloudflare didn't deploy"

Cloudflare Pages needs GitHub app permissions for each private repo.
Usually granted at project creation time, but if a repo went private
AFTER the Cloudflare project was created, permissions may need refresh.

- GitHub → Settings → Applications → **Installed GitHub Apps**
- Find **Cloudflare Pages**
- Configure → Repository access → make sure the affected repo is
  listed under "Only select repositories" (or use "All repositories")
- Save

### "Login page shows but code never arrives"

Check Access application:
- Zero Trust → **Access controls → Applications** → click the app
- **Authentication** section — verify "One-time PIN" is checked under
  "Choose available identity providers"
- If nothing is selected there, no code goes out even to allowlisted
  emails

### "I get a code and enter it but it says 'not authorized'"

The code arrived but the email isn't on the allowlist:
- Zero Trust → **Access controls → Policies → Allowed emails**
- Add the email → Save

### "SSL warning on a subdomain"

Cert is still provisioning after a DNS change. Wait 5 minutes and retry.
If it persists past 15 min:
- Cloudflare → **Workers & Pages → <project> → Custom domains**
- Check the domain status; should be **Active**
- If stuck in "Provisioning" or errored, remove and re-add the domain

### "Someone reports they can't get in"

1. Ask their exact email address (case may matter, or gmail dots)
2. Verify it's on the allowlist (Access → Policies → Allowed emails)
3. If it is: have them clear cookies for `cloudflareaccess.com` and
   try again in a fresh incognito
4. If it isn't: add them and retry

## Cleanup tasks — not urgent

These don't affect functionality but tidy things up:

- [ ] Remove leftover `<!-- deploy test 2026-08-10 -->` HTML comments
      from the bottom of `index.html` in each private repo (added
      during Cloudflare Pages setup to verify deploys were working)
- [ ] Turn off unused GitHub Pages sources on the private repos (for
      those that had it enabled). GitHub → repo → **Settings → Pages
      → Source: None**. Not required — those old deployments can't
      serve private-repo content anyway — but tidier.
- [ ] Rename or reconsider the in-page `<name>_auth` password prompts
      on individual HTML pages. With Cloudflare Access in front, they
      might now feel redundant or, alternatively, could be repurposed
      as "extra-sensitive-page" gates. That's a content decision.

## Historical context

- **Before 2026-08-10:** all four repos were public on GitHub, served
  via GitHub Pages, with only client-side JavaScript password prompts
  on individual pages. The prompts stopped strangers who happened
  onto the URL but the source code was fully public — anyone visiting
  `github.com/bdgroves/brooks-memoir` could read every entry directly.
- **After 2026-08-10:** repos private (source hidden), served via
  Cloudflare Pages (deploy still automatic on push), gated by
  Cloudflare Access (only allowlisted emails can even see the site).

This eliminates the "source is public, site pretends to be gated"
gap. Real security now, not theater.
