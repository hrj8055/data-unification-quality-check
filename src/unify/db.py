"""SQLite storage: one clean table per concern, so every decision can be audited."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SUBMISSIONS_SQL = """
CREATE TABLE IF NOT EXISTS submissions (
    submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT NOT NULL,
    name          TEXT,
    phone         TEXT NOT NULL,
    email         TEXT,
    city          TEXT,
    note          TEXT,
    person_id     INTEGER,
    is_duplicate  INTEGER NOT NULL DEFAULT 0
)"""


def write_database(result, db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    people = pd.DataFrame([{
        "person_id": p.person_id, "name": p.name, "email": p.email, "phone": p.phone,
        "city": p.city, "sources": ", ".join(sorted(p.sources)), "source_count": len(p.sources),
    } for p in result.people])
    tables = {
        "people": people,
        "person_sources": pd.DataFrame(result.links),
        "quality_issues": pd.DataFrame([i.as_dict() for i in result.issues]).astype({"row_number": "Int64"}),
        "quarantine": pd.DataFrame(result.quarantine),
        "change_log": pd.DataFrame(result.changes),
    }
    with sqlite3.connect(db_path) as con:
        for name, df in tables.items():
            df.to_sql(name, con, if_exists="replace", index=False)
        con.execute(SUBMISSIONS_SQL)


def find_person_by_phone(con: sqlite3.Connection, phone: str):
    return con.execute("SELECT person_id, name, city FROM people WHERE phone = ?", (phone,)).fetchone()


def add_submission(db_path: Path, name: str, phone: str, email: str, city: str, note: str,
                   window_hours: int = 24) -> dict:
    """Save a new submission, link it to a known person by phone, and flag repeats.

    A submission is a duplicate when the same phone already submitted within `window_hours`.
    """
    now = datetime.now(timezone.utc)
    with sqlite3.connect(db_path) as con:
        con.execute(SUBMISSIONS_SQL)
        person = find_person_by_phone(con, phone)
        cutoff = (now.timestamp() - window_hours * 3600)
        recent = [r for (r,) in con.execute("SELECT created_at FROM submissions WHERE phone = ?", (phone,))
                  if datetime.fromisoformat(r).timestamp() >= cutoff]
        is_dup = bool(recent)
        cur = con.execute(
            "INSERT INTO submissions (created_at, name, phone, email, city, note, person_id, is_duplicate)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (now.isoformat(), name, phone, email, city, note, person[0] if person else None, int(is_dup)))
        return {"submission_id": cur.lastrowid, "person": person, "is_duplicate": is_dup}
