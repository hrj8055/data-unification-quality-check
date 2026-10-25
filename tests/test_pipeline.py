import csv
import sqlite3

import pytest

from unify.db import add_submission, write_database
from unify.pipeline import Unifier
from unify.quality import ISSUE_TYPES


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


@pytest.fixture
def raw_dir(tmp_path):
    write_csv(tmp_path / "job_portal.csv", [
        ["Full Name", "Email", "Mobile", "City", "Applied Role"],
        ["priya sharma", "PRIYA@example.com", "+91 98765 43210", "delhi", "Data Entry"],
        ["", "", "", "", ""],                                                     # blank
        ["Full Name", "Email", "Mobile", "City", "Applied Role"],                 # repeated header
        ["Rahul Verma", "rahul@example.com", "09123456780", "Pune", "Back Office"],
        ["Rahul Verma", "rahul@example.com", "9123456780", "Pune", "Back Office"],  # duplicate
        ["Bad Row", "not-an-email", "123", "Delhi", "X"],                         # no usable contact
    ])
    write_csv(tmp_path / "gig_workers.csv", [
        ["first_name", "last_name", "phone_no", "email_id", "location", "shifts_done"],
        ["Priya", "Sharma", "9876543210", "", "Delhi", "12"],                   # same person by phone
        ["Verma", "9988776655", "kiran@example.com", "Noida", "4", ""],          # shifted
    ])
    write_csv(tmp_path / "contacts.csv", [
        ["Name", "Phone", "E-mail", "City"],
        ["Mixed Up", "9123456780", "priya@example.com", "Delhi"],                 # conflict
        ["Someone Else", "9876543210", "", "Delhi"],                              # name mismatch
        ["Rahul Verma", "", "rahul.alt@example.com", "Pune"],                     # name+city fallback
    ])
    return tmp_path


def codes(result):
    return {i.code for i in result.issues}


def test_matches_same_person_across_sources(raw_dir):
    r = Unifier().run(raw_dir)
    assert len(r.people) == 2
    priya = next(p for p in r.people if p.name == "Priya Sharma")
    assert priya.sources == {"job_portal", "gig_workers"}
    assert priya.phone == "9876543210" and priya.email == "priya@example.com"


def test_structural_problems_detected(raw_dir):
    found = codes(Unifier().run(raw_dir))
    assert {"BLANK_ROW", "DUPLICATE_HEADER", "DUPLICATE_ROW", "COLUMN_SHIFTED", "MIXED_PHONE_FORMAT"} <= found


def test_unsafe_rows_are_quarantined_not_merged(raw_dir):
    r = Unifier().run(raw_dir)
    reasons = " | ".join(q["reason"] for q in r.quarantine)
    assert "different people" in reasons
    assert "name is completely different" in reasons
    assert "no usable email or phone" in reasons
    assert "column-shifted" in reasons
    assert len(r.quarantine) == 4


def test_name_city_fallback_used_only_without_contact_match(raw_dir):
    r = Unifier().run(raw_dir)
    fallback = [l for l in r.links if l["match_method"] == "name+city fallback"]
    assert len(fallback) == 1 and fallback[0]["email"] == "rahul.alt@example.com"


def test_fallback_blocked_when_phones_differ(tmp_path):
    write_csv(tmp_path / "job_portal.csv", [["Full Name", "Email", "Mobile", "City", "Applied Role"],
                                            ["Amit Kumar", "", "9000000001", "Patna", "x"]])
    write_csv(tmp_path / "gig_workers.csv", [["first_name", "last_name", "phone_no", "email_id", "location", "shifts_done"],
                                             ["Amit", "Kumar", "9000000002", "", "Patna", "1"]])
    write_csv(tmp_path / "contacts.csv", [["Name", "Phone", "E-mail", "City"]])
    assert len(Unifier().run(tmp_path).people) == 2


def test_all_ten_issue_types_documented():
    assert len(ISSUE_TYPES) == 10


def test_database_and_submissions(raw_dir, tmp_path):
    db = tmp_path / "out.db"
    write_database(Unifier().run(raw_dir), db)
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT COUNT(*) FROM people").fetchone()[0] == 2
        assert con.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0] == 4

    first = add_submission(db, "Priya", "9876543210", "", "Delhi", "hello")
    assert first["person"][1] == "Priya Sharma" and not first["is_duplicate"]
    again = add_submission(db, "Priya", "9876543210", "", "Delhi", "again")
    assert again["is_duplicate"]
    unknown = add_submission(db, "New", "9111111111", "", "Pune", "")
    assert unknown["person"] is None
