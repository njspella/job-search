"""Import LinkedIn connections from the Connections.csv in LinkedIn's data export.

LinkedIn has no public API for reading your connections, so the export is the
supported route: LinkedIn > Settings > Data privacy > Get a copy of your data >
Connections. The file starts with a few 'Notes' lines before the real header.
"""

import csv
import io

from .store import company_key


def parse(text):
    lines = text.lstrip("﻿").splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("First Name")), None)
    if start is None:
        raise ValueError("This doesn't look like LinkedIn's Connections.csv (no 'First Name' header found).")
    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
    rows = []
    for r in reader:
        rows.append({
            "first_name": (r.get("First Name") or "").strip(),
            "last_name": (r.get("Last Name") or "").strip(),
            "url": (r.get("URL") or "").strip(),
            "company": (r.get("Company") or "").strip(),
            "position": (r.get("Position") or "").strip(),
            "connected_on": (r.get("Connected On") or "").strip(),
        })
    return rows


def replace_all(db, text):
    """Replace stored connections with a fresh export. Returns the number imported."""
    rows = parse(text)
    db.execute("DELETE FROM connections")
    db.executemany(
        "INSERT INTO connections (first_name, last_name, url, company, company_key, position, connected_on) "
        "VALUES (?,?,?,?,?,?,?)",
        [(r["first_name"], r["last_name"], r["url"], r["company"], company_key(r["company"]),
          r["position"], r["connected_on"]) for r in rows],
    )
    db.commit()
    return len(rows)
