"""Generate three deliberately messy CSV files that describe overlapping people.

The data is synthetic (fake names and numbers) but reproduces the problems found
in real exports: mixed phone formats, upper/lower-case emails, extra spaces,
a repeated header row in the middle of a file, blank rows, rows whose columns
have shifted, and duplicate entries.

Run:  python scripts/generate_sample_data.py
"""
from __future__ import annotations

import csv
import random
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

FIRST = ["Aarav", "Priya", "Rohan", "Sneha", "Vikram", "Ananya", "Karan", "Neha",
         "Arjun", "Pooja", "Rahul", "Kavya", "Aditya", "Isha", "Manish", "Divya",
         "Suresh", "Meera", "Amit", "Ritu"]
LAST = ["Sharma", "Verma", "Gupta", "Singh", "Kumar", "Reddy", "Nair", "Iyer",
        "Patel", "Das", "Yadav", "Mishra"]
CITIES = ["Bengaluru", "Delhi", "Mumbai", "Pune", "Patna", "Hyderabad", "Chennai", "Noida"]


def phone_variants(digits10: str) -> list[str]:
    """Different ways the same mobile number shows up in real spreadsheets."""
    return [
        digits10,
        f"+91{digits10}",
        f"+91 {digits10[:5]} {digits10[5:]}",
        f"0{digits10}",
        f"91-{digits10}",
        f"{digits10[:3]}-{digits10[3:6]}-{digits10[6:]}",
        f"({digits10[:3]}) {digits10[3:6]} {digits10[6:]}",
    ]


def make_people(n: int, rng: random.Random) -> list[dict]:
    people, used = [], set()
    while len(people) < n:
        first, last = rng.choice(FIRST), rng.choice(LAST)
        phone = str(rng.choice([6, 7, 8, 9])) + "".join(str(rng.randint(0, 9)) for _ in range(9))
        if phone in used:
            continue
        used.add(phone)
        people.append({
            "first": first, "last": last,
            "email": f"{first.lower()}.{last.lower()}{rng.randint(1, 99)}@example.com",
            "phone": phone, "city": rng.choice(CITIES),
        })
    return people


def messy_case(text: str, rng: random.Random) -> str:
    return rng.choice([text, text.upper(), text.lower(), f"  {text} ", text.title()])


def main(seed: int = 42) -> None:
    rng = random.Random(seed)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    people = make_people(60, rng)

    # --- Source 1: job portal export --------------------------------------
    job_rows = [["Full Name", "Email", "Mobile", "City", "Applied Role"]]
    for i, p in enumerate(people[:40]):
        job_rows.append([
            messy_case(f"{p['first']} {p['last']}", rng),
            messy_case(p["email"], rng),
            rng.choice(phone_variants(p["phone"])),
            messy_case(p["city"], rng),
            rng.choice(["Delivery Associate", "Data Entry", "Field Executive", "Back Office"]),
        ])
        if i == 15:
            job_rows.append(["Full Name", "Email", "Mobile", "City", "Applied Role"])  # repeated header
        if i in (8, 27):
            job_rows.append(["", "", "", "", ""])                                     # blank row
    job_rows.append(job_rows[5][:])                                                     # exact duplicate
    job_rows.append(["Bad Email Person", "not-an-email", "98765", "Delhi", "Data Entry"])  # invalid email+phone

    # --- Source 2: gig-worker sheet (first/last split, different headers) ---
    gig_rows = [["first_name", "last_name", "phone_no", "email_id", "location", "shifts_done"]]
    for i, p in enumerate(people[25:55]):
        gig_rows.append([
            messy_case(p["first"], rng), messy_case(p["last"], rng),
            rng.choice(phone_variants(p["phone"])),
            messy_case(p["email"], rng) if rng.random() > 0.25 else "",   # some missing emails
            messy_case(p["city"], rng), str(rng.randint(1, 120)),
        ])
        if i == 10:
            # column-shifted row: name missing, everything moved one column left
            gig_rows.append([p["last"], rng.choice(phone_variants(p["phone"])), p["email"], p["city"], "34", ""])
    gig_rows.append(["", "", "", "", "", ""])
    gig_rows.append(["Nobody", "Contact", "", "", "Pune", "3"])                   # no email, no phone

    # --- Source 3: contacts sheet ----------------------------------------
    contact_rows = [["Name", "Phone", "E-mail", "City"]]
    for p in people[45:60] + people[:6]:
        contact_rows.append([
            messy_case(f"{p['first']} {p['last']}", rng),
            rng.choice(phone_variants(p["phone"])),
            messy_case(p["email"], rng),
            messy_case(p["city"], rng),
        ])
    # conflict: email belongs to person 1, phone belongs to person 2
    contact_rows.append(["Mixed Up Record", people[2]["phone"], people[1]["email"], "Delhi"])
    # same phone as an existing person but a completely different name
    contact_rows.append(["Totally Different", people[3]["phone"], "", people[3]["city"]])
    # no email/phone match, but same name + city as an existing person (fallback match)
    p = people[7]
    contact_rows.append([f"{p['first']} {p['last']}", "", f"{p['first'].lower()}.alt@example.com", p["city"]])

    for name, rows in [("job_portal.csv", job_rows), ("gig_workers.csv", gig_rows), ("contacts.csv", contact_rows)]:
        with open(RAW_DIR / name, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)
        print(f"wrote {RAW_DIR / name} ({len(rows) - 1} rows)")


if __name__ == "__main__":
    main()
