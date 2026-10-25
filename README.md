# Data Unification & Quality Check System

This project takes three messy spreadsheets that describe the same people, cleans them, and merges them into one trusted list. Every decision it makes is logged, so you can check it. When a record is unsafe to merge, it goes to a **quarantine** for a person to review instead of being guessed.

This is the same everyday problem that comes up in operations work: partner lists, delivery staff sheets and contact exports. Each one comes from a different place and is formatted differently, and all of them have errors.

## What it does

1. **Reads 3 sources** with different column names: a job-portal export, a gig-worker sheet (where first and last names are separate columns) and a contacts sheet.
2. **Detects 10 types of data-quality issues**, listed in the table below.
3. **Standardises** phone numbers to 10 digits, lower-cases emails, and fixes the spacing and capitalisation of names and cities. Every change is written to a `change_log` table.
4. **Matches people across sources**, first by email or phone number. If neither matches, it falls back to name + city, but only when the phone numbers don't contradict each other.
5. **Quarantines** any row it can't merge safely.
6. **Saves everything to SQLite**: `people`, `person_sources`, `quality_issues`, `quarantine`, `change_log` and `submissions`.
7. **Streamlit dashboard** with an overview, a people search showing where each person came from, the issue list and the quarantine queue. It also has a **submission form** that links each new entry to an existing person by phone number.
8. **n8n workflow** that flags a phone number submitting again within 24 hours.

## The 10 quality checks

| Code | What it means | Action |
|---|---|---|
| `BLANK_ROW` | Row is completely empty | dropped |
| `DUPLICATE_HEADER` | Header row repeated mid-file | dropped |
| `COLUMN_SHIFTED` | Values are in the wrong columns | quarantined |
| `MISSING_CONTACT` | No usable email or phone | quarantined |
| `INVALID_EMAIL` | Email present but invalid | flagged |
| `INVALID_PHONE` | Phone present but not a valid 10-digit mobile | flagged |
| `MIXED_PHONE_FORMAT` | `+91…`, `0…`, `91-…`, dashes, brackets in one file | normalized |
| `DUPLICATE_ROW` | Same person repeated inside one file | dropped |
| `CONFLICTING_MATCH` | Email matches one person, phone matches another | quarantined |
| `NAME_MISMATCH` | Matched by email/phone, but the name is completely different | quarantined |

## Result on the sample data

| | |
|---|---|
| Source rows (3 files) | 102 |
| Rows imported after clean-up | 92 |
| Unique people | 60 |
| People found in 2+ sources | 32 |
| Rows quarantined for review | 5 |
| Issue types detected | 10 of 10 |
| Fields standardised (logged) | 242 |

The sample data is synthetic: the names, emails and numbers are fake. `scripts/generate_sample_data.py` creates it on purpose, with realistic problems built in.

## Run it

```bash
pip install -r requirements.txt

python scripts/generate_sample_data.py                       # create the 3 messy CSVs
PYTHONPATH=src python -m unify.pipeline --raw data/raw --db data/unified.db
streamlit run app/streamlit_app.py                           # open http://localhost:8501
pytest -v                                                    # 13 tests
```

### With Docker (app + n8n)

```bash
docker compose up --build
```

1. Open n8n at http://localhost:5678, then **Import from file** and choose `n8n/duplicate_check_workflow.json`. Activate the workflow.
2. Open the app at http://localhost:8501. Each submission is also sent to the n8n webhook, and the result is shown under the form.

## Project structure

```
src/unify/
  normalize.py   phone, email, name and city rules
  load.py        reads each source and maps its columns to name/email/phone/city
  quality.py     the 10 issue types
  pipeline.py    checks -> standardise -> match -> quarantine (CLI entry point)
  db.py          SQLite tables + submission linking and duplicate check
app/streamlit_app.py
n8n/duplicate_check_workflow.json
scripts/generate_sample_data.py
tests/           13 tests
```

## Tech

Python, Pandas, SQLite, Streamlit, n8n, Docker, Pytest
