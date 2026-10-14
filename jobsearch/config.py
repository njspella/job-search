"""Search settings.

Defaults live here. To change them without editing code, create
`config.local.json` in the repo root with any of the keys in DEFAULTS
(it is git-ignored, so API keys are safe there too).
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

DEFAULTS = {
    # Phrases matched against job titles (case-insensitive).
    "titles": [
        "engineering manager",
        "manager of engineering",
        "manager, engineering",
        "director of engineering",
        "engineering director",
        "head of engineering",
        "principal engineer",
        "principal software engineer",
        "principal mechanical engineer",
        "principal electrical engineer",
        "staff engineer",
        "chief engineer",
        "ai engineer",
        "machine learning engineer",
        "ml engineer",
        "applied scientist",
        "llm engineer",
        "generative ai",
        "quality director",
        "director of quality",
        "director, quality",
        "quality manager",
        "head of quality",
        "vp quality",
        "vp of quality",
        "quality engineering manager",
        "operations manager",
        "director of operations",
        "operations director",
        "director, operations",
        "plant manager",
        "site leader",
        "manufacturing manager",
    ],
    # Titles containing any of these are dropped.
    "exclude_words": ["intern", "internship", "entry level", "sales engineer", "recruiter"],
    # Postings with a listed salary below this are dropped; postings with no
    # salary are kept and flagged.
    "salary_floor": 120000,
    # Home location and how far to look for on-site or hybrid jobs.
    "home": {"name": "Pella, Iowa", "lat": 41.4080, "lon": -92.9163},
    "radius_miles": 45,
    # Towns within roughly a 50-minute drive, used when a posting has no coordinates.
    "nearby_towns": [
        "pella", "knoxville", "oskaloosa", "newton", "indianola", "grinnell",
        "ottumwa", "pleasant hill", "altoona", "des moines", "eddyville",
        "monroe", "prairie city", "carlisle", "norwalk", "chariton", "albia",
        "sully", "lynnville", "colfax", "mitchellville", "bondurant", "ankeny",
        "urbandale", "west des moines", "johnston", "clive",
    ],
    # Searches sent to sources that take a keyword (one request per phrase).
    "queries": [
        "engineering manager",
        "principal engineer",
        "AI engineer",
        "machine learning engineer",
        "quality director",
        "quality manager",
        "operations manager",
        "plant manager",
        "director of engineering",
        "director of operations",
    ],
    "sources": ["remotive", "remoteok", "himalayas", "weworkremotely", "adzuna", "usajobs"],
    # Optional API keys. Environment variables of the same name (upper case) also work.
    "adzuna_app_id": "",
    "adzuna_app_key": "",
    "usajobs_api_key": "",
    "usajobs_email": "",
    "port": 8765,
}


def load():
    cfg = json.loads(json.dumps(DEFAULTS))
    local = ROOT / "config.local.json"
    if local.exists():
        cfg.update(json.loads(local.read_text()))
    for key in ("adzuna_app_id", "adzuna_app_key", "usajobs_api_key", "usajobs_email"):
        env = os.environ.get(key.upper())
        if env:
            cfg[key] = env
    return cfg
