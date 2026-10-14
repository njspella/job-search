"""Adzuna API (free key from https://developer.adzuna.com/). Covers Indeed-style local listings.

Runs each query twice: near home within the radius, and nationwide with 'remote'.
"""

from . import get_json, job

URL = "https://api.adzuna.com/v1/api/jobs/us/search/1"


def parse(data, remote=False):
    out = []
    for j in data.get("results", []):
        title = j.get("title", "")
        desc = (j.get("description") or "").lower()
        is_remote = remote and ("remote" in title.lower() or "remote" in desc)
        if remote and not is_remote:
            continue
        predicted = str(j.get("salary_is_predicted", "0")) == "1"
        out.append(job(
            source="adzuna", source_id=str(j.get("id")), title=title,
            company=(j.get("company") or {}).get("display_name", ""),
            location=(j.get("location") or {}).get("display_name", ""), remote=is_remote,
            salary_min=None if predicted else j.get("salary_min"),
            salary_max=None if predicted else j.get("salary_max"),
            url=j.get("redirect_url", ""), posted=(j.get("created") or "")[:10],
            lat=None if is_remote else j.get("latitude"),
            lon=None if is_remote else j.get("longitude"),
        ))
    return out


def fetch(cfg):
    if not (cfg["adzuna_app_id"] and cfg["adzuna_app_key"]):
        raise RuntimeError("skipped: add adzuna_app_id and adzuna_app_key to config.local.json")
    base = {
        "app_id": cfg["adzuna_app_id"], "app_key": cfg["adzuna_app_key"],
        "results_per_page": 50, "max_days_old": 30, "content-type": "application/json",
    }
    jobs = []
    for q in cfg["queries"]:
        local = dict(base, what_phrase=q, where=cfg["home"]["name"],
                     distance=round(cfg["radius_miles"] * 1.609))
        jobs.extend(parse(get_json(URL, local)))
        remote = dict(base, what_phrase=q, what="remote", salary_min=cfg["salary_floor"])
        jobs.extend(parse(get_json(URL, remote), remote=True))
    return jobs
