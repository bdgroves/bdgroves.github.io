#!/usr/bin/env python3
"""
Build the High Times Top 100 database from CSV seed files.

Usage:  python build.py            # rebuilds hightimes.db from ./data/*.csv
"""
import csv, sqlite3, pathlib, sys

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
DB = HERE / "hightimes.db"

SCHEMA = """
DROP VIEW  IF EXISTS v_entries;
DROP TABLE IF EXISTS entry;
DROP TABLE IF EXISTS installment;
DROP TABLE IF EXISTS issue;

-- One row per magazine issue we know something about.
CREATE TABLE issue (
    issue_id      TEXT PRIMARY KEY,        -- '1988-04'
    year          INTEGER NOT NULL,
    month         INTEGER NOT NULL,
    issue_number  INTEGER,                 -- High Times sequential number, if known
    archive_file  TEXT,                    -- filename in the archive.org 1980s item
    UNIQUE (year, month)
);

-- One row per appearance of the column. format_name tracks the renames.
CREATE TABLE installment (
    installment_id INTEGER PRIMARY KEY,
    issue_id       TEXT NOT NULL REFERENCES issue(issue_id),
    format_name    TEXT NOT NULL,          -- 'Top 40' | 'Top 80' | 'Top 100' | 'NORMLthon' | 'Top 500' | 'Hemp 100' | 'Pot 40'
    slots          INTEGER,                -- nominal number of ranks
    page           INTEGER,
    header_text    TEXT,                   -- the hand-lettered banner
    editor_note    TEXT,                   -- marginalia / editorial intervention
    money_total    REAL,                   -- NORMLthon/Top 500 dollar total
    source         TEXT NOT NULL,          -- 'brooks-photo' | 'archive.org' | 'ht-vault'
    transcribed    INTEGER NOT NULL DEFAULT 0,  -- 1 = full entry list captured
    UNIQUE (issue_id, format_name)
);

-- One row per ranked entry. Only populated for transcribed installments.
CREATE TABLE entry (
    entry_id       INTEGER PRIMARY KEY,
    installment_id INTEGER NOT NULL REFERENCES installment(installment_id),
    rank           INTEGER NOT NULL,
    text           TEXT NOT NULL,          -- entry as printed
    gloss          TEXT,                   -- parenthetical/annotation
    last_month     INTEGER,                -- prior position if bulleted
    amount         REAL,                   -- donation, NORMLthon years
    category       TEXT,                   -- music|politics|cannabis|sex|media|food|people|misc
    UNIQUE (installment_id, rank)
);

CREATE INDEX idx_entry_text ON entry(text);
CREATE INDEX idx_entry_cat  ON entry(category);

CREATE VIEW v_entries AS
SELECT i.year, i.month, i.issue_id, n.format_name, n.page,
       e.rank, e.text, e.gloss, e.last_month, e.category,
       CASE WHEN e.last_month IS NULL THEN NULL
            ELSE e.last_month - e.rank END AS climb
FROM entry e
JOIN installment n ON n.installment_id = e.installment_id
JOIN issue i       ON i.issue_id = n.issue_id;
"""


def load(cur, table, cols):
    path = DATA / f"{table}.csv"
    if not path.exists():
        print(f"  (skip {table}.csv — not present)")
        return 0
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return 0
    placeholders = ",".join("?" * len(cols))
    cur.executemany(
        f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({placeholders})",
        [tuple(r.get(c) or None for c in cols) for r in rows],
    )
    return len(rows)


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.executescript(SCHEMA)

    n = load(cur, "issue", ["issue_id", "year", "month", "issue_number", "archive_file"])
    print(f"issue: {n}")
    n = load(cur, "installment",
             ["installment_id", "issue_id", "format_name", "slots", "page",
              "header_text", "editor_note", "money_total", "source", "transcribed"])
    print(f"installment: {n}")
    n = load(cur, "entry",
             ["entry_id", "installment_id", "rank", "text", "gloss",
              "last_month", "amount", "category"])
    print(f"entry: {n}")

    con.commit()
    print(f"\nwrote {DB}")
    for q, label in [
        ("SELECT COUNT(*) FROM installment", "installments"),
        ("SELECT COUNT(*) FROM entry", "entries"),
        ("SELECT COUNT(DISTINCT format_name) FROM installment", "distinct formats"),
    ]:
        print(f"  {label}: {cur.execute(q).fetchone()[0]}")
    con.close()


if __name__ == "__main__":
    main()
