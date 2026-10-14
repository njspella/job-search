"""Job sources. Each module exposes fetch(cfg) -> list of job dicts with these keys:

source, source_id, title, company, location, remote (bool), salary_min, salary_max,
url, posted (ISO date string or ""), lat, lon (optional).
"""

import json
import urllib.parse
import urllib.request

USER_AGENT = "job-search/1.0 (personal job search tool)"


def get(url, params=None, headers=None, timeout=30):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def get_json(url, params=None, headers=None):
    return json.loads(get(url, params, headers))


def job(**fields):
    base = {
        "source": "", "source_id": "", "title": "", "company": "", "location": "",
        "remote": False, "salary_min": None, "salary_max": None, "url": "",
        "posted": "", "lat": None, "lon": None,
    }
    base.update(fields)
    for k in ("salary_min", "salary_max"):
        if base[k] is not None:
            try:
                base[k] = int(float(base[k])) or None
            except (TypeError, ValueError):
                base[k] = None
    return base
