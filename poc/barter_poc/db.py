"""SQLite storage. One file, created on first run. See docs/design/domain-model.md."""

import json
import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS participants (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    zone         TEXT NOT NULL,
    max_travel   INTEGER NOT NULL DEFAULT 0,
    availability TEXT NOT NULL DEFAULT '[]'          -- JSON list of slots
);

CREATE TABLE IF NOT EXISTS listings (
    id              TEXT PRIMARY KEY,
    participant_id  TEXT NOT NULL REFERENCES participants(id),
    kind            TEXT NOT NULL CHECK (kind IN ('offer', 'need')),
    text            TEXT NOT NULL,
    mode            TEXT NOT NULL DEFAULT 'either',
    effort_hours    REAL,
    concepts        TEXT NOT NULL DEFAULT '[]',      -- JSON list; how it was understood
    concepts_source TEXT NOT NULL DEFAULT 'dictionary', -- dictionary | claude | edited
    status          TEXT NOT NULL DEFAULT 'active',  -- active | held | fulfilled | closed
    held_reason     TEXT
);

CREATE TABLE IF NOT EXISTS blocks (
    blocker_id TEXT NOT NULL,
    blocked_id TEXT NOT NULL,
    PRIMARY KEY (blocker_id, blocked_id)
);

CREATE TABLE IF NOT EXISTS circles (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    status     TEXT NOT NULL,      -- suggested | agreed | paused | completed | dissolved
    confidence REAL NOT NULL,
    signature  TEXT NOT NULL,      -- JSON sorted list of [offer_id, need_id]
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS links (
    circle_id   INTEGER NOT NULL REFERENCES circles(id),
    position    INTEGER NOT NULL,
    giver_id    TEXT NOT NULL,
    receiver_id TEXT NOT NULL,
    offer_id    TEXT NOT NULL,
    need_id     TEXT NOT NULL,
    score       REAL NOT NULL,
    shared      TEXT NOT NULL,     -- JSON list
    mode        TEXT NOT NULL,
    safety      TEXT NOT NULL,     -- JSON list
    received    INTEGER NOT NULL DEFAULT 0,
    note        TEXT,
    PRIMARY KEY (circle_id, position)
);

CREATE TABLE IF NOT EXISTS responses (
    circle_id      INTEGER NOT NULL,
    participant_id TEXT NOT NULL,
    response       TEXT NOT NULL CHECK (response IN ('accepted', 'declined')),
    PRIMARY KEY (circle_id, participant_id)
);

CREATE TABLE IF NOT EXISTS reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id TEXT NOT NULL,
    circle_id   INTEGER,
    reason      TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def connect(path: str) -> sqlite3.Connection:
    if path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def reset(conn: sqlite3.Connection) -> None:
    for table in ("reports", "responses", "links", "circles", "blocks", "listings", "participants"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()


def loads(value):
    return json.loads(value) if value else []


def dumps(value) -> str:
    return json.dumps(sorted(value) if isinstance(value, (set, frozenset)) else value)
