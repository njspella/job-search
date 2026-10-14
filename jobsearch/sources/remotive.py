"""Remotive public API: https://remotive.com/api/remote-jobs (no key; asks for a few calls a day at most)."""

from . import get_json, job
from ..filters import parse_salary

URL = "https://remotive.com/api/remote-jobs"


def parse(data):
    out = []
    for j in data.get("jobs", []):
        lo, hi = parse_salary(j.get("salary"))
        out.append(job(
            source="remotive", source_id=str(j.get("id")), title=j.get("title", ""),
            company=j.get("company_name", ""), location=j.get("candidate_required_location", ""),
            remote=True, salary_min=lo, salary_max=hi, url=j.get("url", ""),
            posted=(j.get("publication_date") or "")[:10],
        ))
    return out


def fetch(cfg):
    jobs = []
    for q in cfg["queries"]:
        jobs.extend(parse(get_json(URL, {"search": q, "limit": 100})))
    return jobs
