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


def export(path, cfg, fetchers=None):
    """Fetch every source and merge matches into a JSON file. Jobs already in the
    file are kept, so the file only grows. Used by the GitHub Actions refresh,
    which feeds the hosted website. Returns the same report shape as run()."""
    import hashlib
    from pathlib import Path

    path = Path(path)
    existing = json.loads(path.read_text()) if path.exists() else {"jobs": []}
    by_id = {j["id"]: j for j in existing["jobs"]}
    report = {"added": 0, "seen": 0, "sources": {}}
    started = store.now()
    for name in cfg["sources"]:
        try:
            fetch = (fetchers or {}).get(name) or importlib.import_module(f".sources.{name}", __package__).fetch
            found = fetch(cfg)
        except Exception as e:
            report["sources"][name] = str(e) if str(e).startswith("skipped") else f"error: {e}"
            continue
        matched = [j for j in found if filters.keep(j, cfg)]
        for j in matched:
            jid = hashlib.sha1(store.dedupe_key(j).encode()).hexdigest()[:16]
            if jid in by_id:
                report["seen"] += 1
                by_id[jid]["last_seen"] = started
                continue
            report["added"] += 1
            by_id[jid] = {
                "id": jid, "title": j["title"], "company": j["company"], "location": j["location"],
                "remote": bool(j["remote"]), "salary_min": j["salary_min"], "salary_max": j["salary_max"],
                "url": j["url"], "source": j["source"], "posted": j["posted"],
                "first_seen": started, "last_seen": started,
            }
        report["sources"][name] = f"ok: {len(matched)} of {len(found)} matched"
    jobs = sorted(by_id.values(), key=lambda j: j["first_seen"], reverse=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"refreshed_at": started, "report": report, "jobs": jobs}, indent=1))
    return report


def new_docs(jobs_path, existing_ids, out_dir):
    """Write one JSON file per job in jobs_path whose id is not in existing_ids,
    ready to send to the website's database. Returns the ids written, newest first."""
    from pathlib import Path

    data = json.loads(Path(jobs_path).read_text())
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for j in data["jobs"]:
        if j["id"] in existing_ids:
            continue
        doc = {k: v for k, v in j.items() if k != "id"}
        doc.update(status="New", notes="")
        (out / f"{j['id']}.json").write_text(json.dumps(doc))
        written.append(j["id"])
    return written
