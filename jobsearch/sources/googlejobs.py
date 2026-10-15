"""Google Jobs through SerpApi (key from https://serpapi.com/). Google Jobs indexes
listings from LinkedIn, Indeed, Glassdoor, ZipRecruiter and company sites, so this is
how postings from those sites reach the tracker without scraping them.

SerpApi's free plan has a monthly search limit, so this source sends a few combined
queries per run (the `google_jobs_queries` setting): one local search and one remote
search for each.
"""

import json
import urllib.error

from . import get_json, job
from ..filters import parse_salary

URL = "https://serpapi.com/search.json"
# A fresh (uncached) Google Jobs search often takes 30-60 seconds on SerpApi's side.
TIMEOUT = 120
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
    searches = []
    for q in cfg["google_jobs_queries"]:
        # Results are narrowed to the drive radius afterwards by filters.location_ok.
        searches.append(({"engine": "google_jobs", "q": f"{q} near Pella, IA",
                          "location": "Iowa, United States", "api_key": key}, False))
        searches.append(({"engine": "google_jobs", "q": f"{q} remote", "location": "United States",
                          "ltype": 1, "api_key": key}, True))
    jobs, errors = [], []
    for params, remote in searches:
        # One slow or failed search shouldn't lose the others; retry each once.
        for attempt in (1, 2):
            try:
                data = get_json(URL, params, timeout=TIMEOUT)
                break
            except urllib.error.HTTPError as e:
                # SerpApi explains bad requests in a JSON body; retrying won't help.
                try:
                    data = json.loads(e.read().decode("utf-8", errors="replace"))
                except ValueError:
                    data = {"error": str(e)}
                break
            except Exception as e:
                data = None
                if attempt == 2:
                    errors.append(f"{params['q']!r}: {e}")
        if data is None:
            continue
        if data.get("error") and "hasn't returned any results" not in str(data["error"]):
            errors.append(f"{params['q']!r}: {data['error']}")
            continue
        jobs.extend(parse(data, remote=remote))
    if errors and len(errors) == len(searches):
        raise RuntimeError("all Google Jobs searches failed; first error " + errors[0])
    if errors:
        print(f"googlejobs: {len(errors)} of {len(searches)} searches failed: {errors}")
    return jobs
