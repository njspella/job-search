"""USAJOBS API (free key from https://developer.usajobs.gov/)."""

from . import get_json, job

URL = "https://data.usajobs.gov/api/search"


def parse(data, remote=False):
    out = []
    items = (data.get("SearchResult") or {}).get("SearchResultItems") or []
    for item in items:
        d = item.get("MatchedObjectDescriptor") or {}
        pay = (d.get("PositionRemuneration") or [{}])[0]
        annual = pay.get("RateIntervalCode") in ("PA", "Per Year")
        loc = (d.get("PositionLocation") or [{}])[0]
        out.append(job(
            source="usajobs", source_id=str(d.get("PositionID") or d.get("PositionURI")),
            title=d.get("PositionTitle", ""), company=d.get("OrganizationName", ""),
            location=d.get("PositionLocationDisplay", ""), remote=remote,
            salary_min=pay.get("MinimumRange") if annual else None,
            salary_max=pay.get("MaximumRange") if annual else None,
            url=d.get("PositionURI", ""), posted=(d.get("PublicationStartDate") or "")[:10],
            lat=None if remote else loc.get("Latitude"), lon=None if remote else loc.get("Longitude"),
        ))
    return out


def fetch(cfg):
    if not (cfg["usajobs_api_key"] and cfg["usajobs_email"]):
        raise RuntimeError("skipped: needs a free USAJOBS API key (see README)")
    headers = {"Host": "data.usajobs.gov", "User-Agent": cfg["usajobs_email"],
               "Authorization-Key": cfg["usajobs_api_key"]}
    jobs = []
    for q in cfg["queries"]:
        common = {"Keyword": q, "RemunerationMinimumAmount": cfg["salary_floor"], "ResultsPerPage": 100}
        jobs.extend(parse(get_json(URL, dict(common, LocationName=cfg["home"]["name"],
                                              Radius=cfg["radius_miles"]), headers)))
        jobs.extend(parse(get_json(URL, dict(common, RemoteIndicator="True"), headers), remote=True))
    return jobs
