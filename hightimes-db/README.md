# High Times "Top 100" database

A relational record of the reader-voted back-page column John Holmstrom ran in
*High Times*, September 1986 – at least January 2012, under four names.

## Files

| File | What it is |
|---|---|
| `hightimes.db` | SQLite database (build output) |
| `build.py` | Schema + loader. `python build.py` rebuilds the DB from `data/*.csv` |
| `data/issue.csv` | One row per issue we've touched |
| `data/installment.csv` | One row per appearance of the column |
| `data/entry.csv` | One row per ranked entry |

CSVs are the source of truth; the DB is disposable. Edit CSVs, re-run `build.py`.

## Schema

```
issue        issue_id (1988-04), year, month, issue_number, archive_file
installment  installment_id, issue_id, format_name, slots, page,
             header_text, editor_note, money_total, source, transcribed
entry        entry_id, installment_id, rank, text, gloss,
             last_month, amount, category
v_entries    flattened join, plus computed `climb` (last_month - rank)
```

`source` is one of `brooks-photo`, `archive.org`, `ht-vault` — so provenance
survives. `transcribed = 1` means the full entry list is captured; `0` means we
have the installment's metadata only.

## Current coverage

- **37 installments** identified, spanning 1986–2012
- **6 fully transcribed** (478 entries): Jan 1987, Mar 1987, Aug 1987,
  Oct 1987, Nov 1987, Apr 1988 — all from Brooks's own copies
- **7 format names**: Top 40, Top 80, Top 100, NORMLthon, Top 500, Hemp 100, Pot 40

## Caveats

- `category` is auto-assigned by regex in a first pass. Treat as a draft;
  ~29% land in `misc` and some assignments are wrong (`Love` the band vs.
  love the concept). Hand-correct as you use it.
- `last_month` is only present where the printed page showed a bullet.
- Entry text is normalized lightly (ampersands, capitalization) — the
  transcription in `high-times-top-100-source-notes.md` is closer to the page.
- Two 1987 installments print 98 and 99 slots rather than a clean 100;
  ranks follow the page, not arithmetic.

## Sample queries

```sql
-- What charted in every transcribed issue?
SELECT text, COUNT(DISTINCT installment_id) n FROM entry
GROUP BY LOWER(text) HAVING n >= 4 ORDER BY n DESC;

-- Political content as a share of each list
SELECT issue_id, ROUND(100.0*SUM(category='politics')/COUNT(*),1) pct_politics
FROM v_entries GROUP BY issue_id ORDER BY issue_id;

-- Chart movement
SELECT text, last_month, rank, climb FROM v_entries
WHERE climb IS NOT NULL ORDER BY climb DESC LIMIT 20;

-- The format timeline
SELECT format_name, MIN(issue_id) first, MAX(issue_id) last, COUNT(*) n
FROM installment GROUP BY format_name ORDER BY first;
```
