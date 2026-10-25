"""The 10 data-quality checks, and what the pipeline does when each one fires."""
from __future__ import annotations

from dataclasses import dataclass

# code -> (severity, action, plain-English meaning)
ISSUE_TYPES = {
    "BLANK_ROW":          ("low",    "dropped",     "Row has no values at all"),
    "DUPLICATE_HEADER":   ("low",    "dropped",     "Header row repeated in the middle of the file"),
    "COLUMN_SHIFTED":     ("high",   "quarantined", "Values sit in the wrong columns (row shifted)"),
    "MISSING_CONTACT":    ("high",   "quarantined", "No usable email or phone, so the person can't be identified"),
    "INVALID_EMAIL":      ("medium", "flagged",     "Email is present but not a valid address"),
    "INVALID_PHONE":      ("medium", "flagged",     "Phone is present but not a valid 10-digit mobile number"),
    "MIXED_PHONE_FORMAT": ("low",    "normalized",  "Phone numbers written in several formats in one file"),
    "DUPLICATE_ROW":      ("low",    "dropped",     "Same person repeated within the same file"),
    "CONFLICTING_MATCH":  ("high",   "quarantined", "Email matches one person but phone matches another"),
    "NAME_MISMATCH":      ("high",   "quarantined", "Email/phone matches a person whose name is completely different"),
}


@dataclass
class Issue:
    source: str
    row_number: int | None
    code: str
    detail: str

    @property
    def severity(self) -> str:
        return ISSUE_TYPES[self.code][0]

    @property
    def action(self) -> str:
        return ISSUE_TYPES[self.code][1]

    def as_dict(self) -> dict:
        return {"source": self.source, "row_number": self.row_number, "issue_code": self.code,
                "severity": self.severity, "action": self.action, "detail": self.detail}
