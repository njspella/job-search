"""Decide which postings match the search criteria."""

import math
import re

REMOTE_OK_REGIONS = (
    "anywhere", "worldwide", "global", "usa", "us", "u.s.", "united states",
    "north america", "americas", "remote", "us only", "usa only",
)


def title_matches(title, cfg):
    t = (title or "").lower()
    if any(word in t for word in cfg["exclude_words"]):
        return False
    return any(phrase in t for phrase in cfg["titles"])


def salary_ok(job, cfg):
    """Unknown salary passes (flagged in the UI); a known salary must reach the floor."""
    top = job.get("salary_max") or job.get("salary_min")
    if not top:
        return True
    return top >= cfg["salary_floor"]


def miles_between(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def remote_region_ok(region):
    """Remote jobs must be open to someone living in Iowa."""
    if not region:
        return True
    parts = [p.strip().lower() for p in re.split(r"[,/;|]| or ", region)]
    return any(p in REMOTE_OK_REGIONS or "united states" in p or "usa" in p
               or "north america" in p or "americas" in p or "iowa" in p
               or "anywhere" in p or "worldwide" in p for p in parts)


def location_ok(job, cfg):
    if job.get("remote"):
        return remote_region_ok(job.get("location"))
    lat, lon = job.get("lat"), job.get("lon")
    if lat is not None and lon is not None:
        home = cfg["home"]
        return miles_between(home["lat"], home["lon"], lat, lon) <= cfg["radius_miles"]
    loc = (job.get("location") or "").lower()
    if not loc:
        return False
    in_iowa = "iowa" in loc or re.search(r"\bia\b", loc)
    return bool(in_iowa) and any(re.search(rf"\b{re.escape(t)}\b", loc) for t in cfg["nearby_towns"])


def keep(job, cfg):
    return title_matches(job.get("title"), cfg) and salary_ok(job, cfg) and location_ok(job, cfg)


_MONEY = re.compile(r"\$?\s*(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(k|K)?")


def parse_salary(text):
    """Pull an annual (min, max) out of free text like '$150k - $180k'. Returns (None, None) if unclear."""
    if not text:
        return None, None
    values = []
    for num, k in _MONEY.findall(str(text)):
        v = float(num.replace(",", ""))
        if k:
            v *= 1000
        if 20000 <= v <= 1000000:
            values.append(int(v))
    if not values:
        return None, None
    return min(values), max(values)
