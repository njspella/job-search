"""Pull every source, filter, and merge into the saved job list."""

import importlib
import json

from . import filters, store


def run(db, cfg, fetchers=None):
    """Returns a report: {added, seen, sources: {name: 'ok: N matched' | error text}}."""
    report = {"added": 0, "seen": 0, "sources": {}}
    started = store.now()  # jobs first seen at or after this are "new this refresh"
    for name in cfg["sources"]:
        try:
            fetch = (fetchers or {}).get(name) or importlib.import_module(f".sources.{name}", __package__).fetch
            found = fetch(cfg)
        except Exception as e:  # one broken source shouldn't stop the others
            report["sources"][name] = str(e) if str(e).startswith("skipped") else f"error: {e}"
            continue
        matched = [j for j in found if filters.keep(j, cfg)]
        for j in matched:
            if store.upsert_job(db, j):
                report["added"] += 1
            else:
                report["seen"] += 1
        report["sources"][name] = f"ok: {len(matched)} of {len(found)} matched"
    db.execute("INSERT INTO refreshes (ran_at, added, seen, report) VALUES (?,?,?,?)",
               (started, report["added"], report["seen"], json.dumps(report["sources"])))
    db.commit()
    return report
