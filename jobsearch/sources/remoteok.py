"""Remote OK public API: https://remoteok.com/api (no key). The first element is a legal notice."""

from . import get_json, job

URL = "https://remoteok.com/api"


def parse(data):
    out = []
    for j in data:
        if not isinstance(j, dict) or "position" not in j:
            continue
        out.append(job(
            source="remoteok", source_id=str(j.get("id")), title=j.get("position", ""),
            company=j.get("company", ""), location=j.get("location", ""), remote=True,
            salary_min=j.get("salary_min"), salary_max=j.get("salary_max"),
            url=j.get("url") or j.get("apply_url", ""), posted=(j.get("date") or "")[:10],
        ))
    return out


def fetch(cfg):
    return parse(get_json(URL))
