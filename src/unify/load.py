"""Read each source CSV and map its own column names onto one standard layout.

Rows are read as raw lists (not straight into a DataFrame) so that structural
problems such as repeated headers, blank rows and shifted columns can be
detected instead of silently breaking the import.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

STANDARD_FIELDS = ["name", "email", "phone", "city"]


@dataclass
class SourceSpec:
    name: str
    file: str
    # standard field -> column(s) in this file. A list means "join these columns".
    columns: dict[str, str | list[str]]


SOURCES = [
    SourceSpec("job_portal", "job_portal.csv",
               {"name": "Full Name", "email": "Email", "phone": "Mobile", "city": "City"}),
    SourceSpec("gig_workers", "gig_workers.csv",
               {"name": ["first_name", "last_name"], "email": "email_id", "phone": "phone_no", "city": "location"}),
    SourceSpec("contacts", "contacts.csv",
               {"name": "Name", "email": "E-mail", "phone": "Phone", "city": "City"}),
]


@dataclass
class RawRow:
    source: str
    row_number: int          # line number in the file (header = 1)
    values: list[str]
    record: dict = field(default_factory=dict)   # filled with standard fields


def read_source(raw_dir: Path, spec: SourceSpec) -> tuple[list[str], list[RawRow]]:
    with open(raw_dir / spec.file, newline="", encoding="utf-8") as f:
        lines = list(csv.reader(f))
    header, body = lines[0], lines[1:]
    index = {col.strip(): i for i, col in enumerate(header)}

    rows = []
    for offset, values in enumerate(body, start=2):
        values = values + [""] * (len(header) - len(values))   # pad short rows
        record = {}
        for std, cols in spec.columns.items():
            cols = cols if isinstance(cols, list) else [cols]
            record[std] = " ".join(values[index[c]] for c in cols if values[index[c]].strip())
        rows.append(RawRow(spec.name, offset, values, record))
    return header, rows
