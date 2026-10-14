"""SQLite storage. Refreshing only adds or updates postings; nothing is deleted,
so your status and notes on a job survive every refresh."""

import datetime
import re
import sqlite3

from .config import DATA_DIR

STATUSES = ["New", "Saved", "Applied", "Interviewing", "Offer", "Rejected", "Not interested"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    dedupe_key TEXT UNIQUE NOT NULL,
    source TEXT, source_id TEXT, title TEXT, company TEXT, location TEXT,
    remote INTEGER, salary_min INTEGER, salary_max INTEGER, url TEXT, posted TEXT,
    first_seen TEXT, last_seen TEXT,
    status TEXT DEFAULT 'New', status_changed TEXT, notes TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS connections (
    id INTEGER PRIMARY KEY,
    first_name TEXT, last_name TEXT, url TEXT, company TEXT, company_key TEXT,
    position TEXT, connected_on TEXT
);
CREATE INDEX IF NOT EXISTS connections_company ON connections(company_key);
CREATE TABLE IF NOT EXISTS refreshes (
    id INTEGER PRIMARY KEY, ran_at TEXT, added INTEGER, seen INTEGER, report TEXT
);
"""

_SUFFIXES = re.compile(
    r"\b(inc|incorporated|llc|l\.l\.c|ltd|limited|corp|corporation|co|company|"
    r"plc|lp|llp|group|holdings|the)\b\.?"
)


def company_key(name):
    """Normalize a company name so 'Vermeer Corporation' and 'Vermeer Corp.' match."""
    s = (name or "").lower().replace("&", " and ")
    s = _SUFFIXES.sub(" ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def dedupe_key(job):
    title = re.sub(r"[^a-z0-9]+", " ", (job.get("title") or "").lower()).strip()
    return f"{company_key(job.get('company'))}|{title}|{'remote' if job.get('remote') else 'onsite'}"


def connect(path=None):
    DATA_DIR.mkdir(exist_ok=True)
    db = sqlite3.connect(path or DATA_DIR / "jobs.db", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def upsert_job(db, job):
    """Insert a new posting or refresh last_seen on a known one. Returns True if new."""
    key = dedupe_key(job)
    ts = now()
    row = db.execute("SELECT id, salary_min, salary_max FROM jobs WHERE dedupe_key = ?", (key,)).fetchone()
    if row:
        db.execute(
            "UPDATE jobs SET last_seen = ?, salary_min = COALESCE(salary_min, ?), "
            "salary_max = COALESCE(salary_max, ?) WHERE id = ?",
            (ts, job.get("salary_min"), job.get("salary_max"), row["id"]),
        )
        return False
    db.execute(
        "INSERT INTO jobs (dedupe_key, source, source_id, title, company, location, remote, "
        "salary_min, salary_max, url, posted, first_seen, last_seen) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (key, job.get("source"), job.get("source_id"), job.get("title"), job.get("company"),
         job.get("location"), int(bool(job.get("remote"))), job.get("salary_min"),
         job.get("salary_max"), job.get("url"), job.get("posted"), ts, ts),
    )
    return True


def update_job(db, job_id, status=None, notes=None):
    if status is not None:
        if status not in STATUSES:
            raise ValueError(f"unknown status {status!r}")
        db.execute("UPDATE jobs SET status = ?, status_changed = ? WHERE id = ?", (status, now(), job_id))
    if notes is not None:
        db.execute("UPDATE jobs SET notes = ? WHERE id = ?", (notes, job_id))
    db.commit()


def list_jobs(db):
    jobs = [dict(r) for r in db.execute("SELECT * FROM jobs ORDER BY first_seen DESC, id DESC")]
    people = {}
    for c in db.execute("SELECT * FROM connections WHERE company_key != ''"):
        people.setdefault(c["company_key"], []).append({
            "name": f"{c['first_name']} {c['last_name']}".strip(),
            "position": c["position"], "url": c["url"],
        })
    for j in jobs:
        j["remote"] = bool(j["remote"])
        j["connections"] = people.get(company_key(j["company"]), [])
    return jobs


def last_refresh(db):
    row = db.execute("SELECT * FROM refreshes ORDER BY id DESC LIMIT 1").fetchone()
    return dict(row) if row else None
