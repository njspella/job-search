"""Google Jobs through SerpApi (key from https://serpapi.com/). Google Jobs indexes
listings from LinkedIn, Indeed, Glassdoor, ZipRecruiter and company sites, so this is
how postings from those sites reach the tracker without scraping them.

SerpApi's free plan has a monthly search limit, so this source sends a few combined
queries per run (the `google_jobs_queries` setting): one local search and one remote
search for each.
"""

from . import get_json, job
from ..filters import parse_salary

URL = "https://serpapi.com/search.json"
PREFERRED = ("linkedin", "indeed", "glassdoor")


def _pick_link(j):
    options = j.get("apply_options") or []
    for name in PREFERRED:
        for o in options:
            if name in (o.get("title") or "").lower() and o.get("link"):
                return o["link"], o["title"]
    if options and options[0].get("link"):
        return options[0]["link"], options[0].get("title") or ""
    return j.get("share_link", ""), ""


def parse(data, remote=False):
    out = []
    for j in data.get("jobs_results", []):
        ext = j.get("detected_extensions") or {}
        link, via = _pick_link(j)
        via = via or (j.get("via") or "").replace("via ", "")
        lo, hi = parse_salary(ext.get("salary"))
        if ext.get("salary") and "hour" in str(ext.get("salary")).lower():
            lo = hi = None
        is_remote = remote or bool(ext.get("work_from_home"))
        out.append(job(
            source=via or "Google Jobs", source_id=j.get("job_id") or link, title=j.get("title", ""),
            company=j.get("company_name", ""), location=j.get("location", ""), remote=is_remote,
            salary_min=lo, salary_max=hi, url=link,
        ))
    return out


def fetch(cfg):
    key = cfg.get("serpapi_key")
    if not key:
        raise RuntimeError("skipped: needs a SerpApi key for LinkedIn, Indeed and Glassdoor listings (see README)")
    jobs = []
    for q in cfg["google_jobs_queries"]:
        local = {"engine": "google_jobs", "q": q, "location": "Pella, Iowa, United States",
                 "lrad": round(cfg["radius_miles"] * 1.609), "api_key": key}
        jobs.extend(parse(get_json(URL, local)))
        remote = {"engine": "google_jobs", "q": f"{q} remote", "location": "United States",
                  "ltype": 1, "api_key": key}
        jobs.extend(parse(get_json(URL, remote), remote=True))
    return jobs
