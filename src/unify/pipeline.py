"""Run the full clean-up: read 3 sources -> check quality -> standardise -> match -> save to SQLite.

Usage:
    python -m unify.pipeline --raw data/raw --db data/unified.db
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .db import write_database
from .load import SOURCES, RawRow, read_source
from .normalize import (clean_text, name_similarity, normalize_city, normalize_email,
                        normalize_name, normalize_phone, phone_format)
from .quality import Issue


@dataclass
class Person:
    person_id: int
    name: str
    email: str
    phone: str
    city: str
    sources: set = field(default_factory=set)


@dataclass
class Result:
    people: list[Person] = field(default_factory=list)
    links: list[dict] = field(default_factory=list)       # which source row became which person
    issues: list[Issue] = field(default_factory=list)
    quarantine: list[dict] = field(default_factory=list)
    changes: list[dict] = field(default_factory=list)


class Unifier:
    def __init__(self) -> None:
        self.r = Result()
        self.by_email: dict[str, Person] = {}
        self.by_phone: dict[str, Person] = {}
        self.by_name_city: dict[tuple[str, str], Person] = {}

    # ---- helpers ---------------------------------------------------------
    def issue(self, row: RawRow | None, code: str, detail: str, source: str | None = None) -> None:
        self.r.issues.append(Issue(source or row.source, row.row_number if row else None, code, detail))

    def quarantine(self, row: RawRow, reason: str) -> None:
        self.r.quarantine.append({"source": row.source, "row_number": row.row_number,
                                  "reason": reason, "raw_values": json.dumps(row.values)})

    def log_changes(self, row: RawRow, clean: dict) -> None:
        for fld, new in clean.items():
            old = row.record.get(fld, "")
            if new and old != new:
                self.r.changes.append({"source": row.source, "row_number": row.row_number,
                                       "field": fld, "old_value": old, "new_value": new})

    def index(self, p: Person) -> None:
        if p.email:
            self.by_email.setdefault(p.email, p)
        if p.phone:
            self.by_phone.setdefault(p.phone, p)
        if p.name and p.city:
            self.by_name_city.setdefault((p.name.lower(), p.city.lower()), p)

    # ---- structural checks (before any cleaning) -------------------------
    def structural_problem(self, row: RawRow, header: list[str]) -> bool:
        vals = [clean_text(v) for v in row.values]
        if not any(vals):
            self.issue(row, "BLANK_ROW", "empty row removed")
            return True
        if [v.lower() for v in vals[:len(header)]] == [h.strip().lower() for h in header]:
            self.issue(row, "DUPLICATE_HEADER", "repeated header removed")
            return True
        rec = row.record
        email_elsewhere = "@" not in rec["email"] and any("@" in v for v in vals)
        phone_elsewhere = (not normalize_phone(rec["phone"])
                           and any(normalize_phone(v) for v in vals if "@" not in v))
        if email_elsewhere or phone_elsewhere:
            self.issue(row, "COLUMN_SHIFTED", f"values found in wrong columns: {vals}")
            self.quarantine(row, "column-shifted row; fix by hand before importing")
            return True
        return False

    # ---- main matching step ----------------------------------------------
    def add_row(self, row: RawRow) -> None:
        rec = row.record
        clean = {"name": normalize_name(rec["name"]), "email": normalize_email(rec["email"]),
                 "phone": normalize_phone(rec["phone"]), "city": normalize_city(rec["city"])}

        if clean_text(rec["email"]) and not clean["email"]:
            self.issue(row, "INVALID_EMAIL", f"'{rec['email']}' is not a valid email")
        if clean_text(rec["phone"]) and not clean["phone"]:
            self.issue(row, "INVALID_PHONE", f"'{rec['phone']}' is not a valid mobile number")
        if not clean["email"] and not clean["phone"]:
            self.issue(row, "MISSING_CONTACT", f"{clean['name'] or 'unnamed'} has no usable email or phone")
            self.quarantine(row, "no usable email or phone")
            return

        by_email = self.by_email.get(clean["email"]) if clean["email"] else None
        by_phone = self.by_phone.get(clean["phone"]) if clean["phone"] else None

        if by_email and by_phone and by_email is not by_phone:
            self.issue(row, "CONFLICTING_MATCH",
                       f"email matches #{by_email.person_id} {by_email.name}, phone matches #{by_phone.person_id} {by_phone.name}")
            self.quarantine(row, "email and phone point to different people")
            return

        match, method = by_email or by_phone, None
        if match:
            method = "email+phone" if (by_email and by_phone) else ("email" if by_email else "phone")
            if clean["name"] and match.name and name_similarity(clean["name"], match.name) == 0:
                self.issue(row, "NAME_MISMATCH",
                           f"'{clean['name']}' matched #{match.person_id} '{match.name}' by {method}")
                self.quarantine(row, f"matched by {method} but name is completely different")
                return
            if row.source in match.sources and self._same_as_existing(match, clean):
                self.issue(row, "DUPLICATE_ROW", f"repeat of person #{match.person_id} in {row.source}")
                return
        elif clean["name"] and clean["city"]:
            match = self.by_name_city.get((clean["name"].lower(), clean["city"].lower()))
            # Two people can share a common name in the same city. Only trust the
            # fallback when the phone numbers don't contradict each other.
            if match and clean["phone"] and match.phone and clean["phone"] != match.phone:
                match = None
            if match:
                method = "name+city fallback"

        self.log_changes(row, clean)
        if match:
            for fld in ("email", "phone", "city", "name"):
                if not getattr(match, fld) and clean[fld]:
                    setattr(match, fld, clean[fld])
            person = match
        else:
            person = Person(len(self.r.people) + 1, clean["name"], clean["email"], clean["phone"], clean["city"])
            self.r.people.append(person)
            method = "new person"
        person.sources.add(row.source)
        self.index(person)
        self.r.links.append({"person_id": person.person_id, "source": row.source,
                             "row_number": row.row_number, "match_method": method, **clean})

    @staticmethod
    def _same_as_existing(p: Person, clean: dict) -> bool:
        return all(not clean[f] or clean[f] == getattr(p, f) for f in ("email", "phone"))

    # ---- whole run --------------------------------------------------------
    def run(self, raw_dir: Path) -> Result:
        for spec in SOURCES:
            header, rows = read_source(raw_dir, spec)
            formats = Counter(phone_format(r.record["phone"]) for r in rows
                              if normalize_phone(r.record["phone"]))
            if len(formats) > 1:
                summary = ", ".join(f"{k}: {v}" for k, v in formats.most_common())
                self.issue(None, "MIXED_PHONE_FORMAT", f"{len(formats)} formats ({summary}) -> all set to 10 digits",
                           source=spec.name)
            for row in rows:
                if not self.structural_problem(row, header):
                    self.add_row(row)
        return self.r


def summarize(r: Result) -> dict:
    issues = pd.DataFrame([i.as_dict() for i in r.issues])
    links = pd.DataFrame(r.links)
    return {
        "source_rows_imported": len(r.links),
        "unique_people": len(r.people),
        "people_in_2plus_sources": sum(len(p.sources) > 1 for p in r.people),
        "quarantined_rows": len(r.quarantine),
        "issue_types_found": int(issues["issue_code"].nunique()) if len(issues) else 0,
        "issues_by_type": issues["issue_code"].value_counts().to_dict() if len(issues) else {},
        "match_methods": links["match_method"].value_counts().to_dict() if len(links) else {},
        "fields_standardised": len(r.changes),
    }


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", default="data/raw", type=Path)
    ap.add_argument("--db", default="data/unified.db", type=Path)
    args = ap.parse_args(argv)

    result = Unifier().run(args.raw)
    write_database(result, args.db)
    summary = summarize(result)
    print(json.dumps(summary, indent=2))
    print(f"\nSaved to {args.db}")
    return summary


if __name__ == "__main__":
    main()
