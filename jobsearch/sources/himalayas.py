"""Himalayas public API: https://himalayas.app/jobs/api (no key). Pages through the newest postings."""

import datetime

from . import get_json, job

URL = "https://himalayas.app/jobs/api"
PAGES = 5
PAGE_SIZE = 20


def parse(data):
    out = []
    for j in data.get("jobs", []):
        posted = j.get("pubDate")
        if isinstance(posted, (int, float)):
            posted = datetime.datetime.fromtimestamp(posted, datetime.timezone.utc).date().isoformat()
        out.append(job(
            source="himalayas", source_id=str(j.get("guid") or j.get("applicationLink")),
            title=j.get("title", ""), company=j.get("companyName", ""),
            location=", ".join(j.get("locationRestrictions") or []), remote=True,
            salary_min=j.get("minSalary"), salary_max=j.get("maxSalary"),
            url=j.get("applicationLink") or j.get("guid", ""), posted=str(posted or "")[:10],
        ))
    return out


def fetch(cfg):
    jobs = []
    for page in range(PAGES):
        batch = parse(get_json(URL, {"limit": PAGE_SIZE, "offset": page * PAGE_SIZE}))
        jobs.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
    return jobs
