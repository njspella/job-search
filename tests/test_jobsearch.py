import json
import sqlite3
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from jobsearch import config, connections, filters, refresh, server, store
from jobsearch.sources import adzuna, himalayas, remoteok, remotive, usajobs, weworkremotely

CFG = config.load()
CFG["sources"] = ["fake"]

CONNECTIONS_CSV = """Notes:
"When exporting your connection data, you may notice that some of the email addresses are missing."

First Name,Last Name,URL,Email Address,Company,Position,Connected On
Jane,Doe,https://www.linkedin.com/in/janedoe,,Vermeer Corporation,Quality Engineer,01 Mar 2022
Sam,Lee,https://www.linkedin.com/in/samlee,,"Acme, Inc.",Director,05 Jun 2021
"""


def memdb():
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(store.SCHEMA)
    return db


def j(**kw):
    from jobsearch.sources import job
    return job(**{"source": "fake", "source_id": "1", "company": "Vermeer Corp.", **kw})


class FilterTests(unittest.TestCase):
    def test_titles(self):
        self.assertTrue(filters.title_matches("Senior Engineering Manager, Platform", CFG))
        self.assertTrue(filters.title_matches("Director of Quality", CFG))
        self.assertFalse(filters.title_matches("Engineering Manager Intern", CFG))
        self.assertFalse(filters.title_matches("Software Engineer", CFG))

    def test_salary(self):
        self.assertTrue(filters.salary_ok({"salary_min": None, "salary_max": None}, CFG))
        self.assertTrue(filters.salary_ok({"salary_min": 110000, "salary_max": 140000}, CFG))
        self.assertFalse(filters.salary_ok({"salary_min": 80000, "salary_max": 100000}, CFG))
        self.assertEqual(filters.parse_salary("$150k - $180k"), (150000, 180000))
        self.assertEqual(filters.parse_salary("USD 130,000"), (130000, 130000))
        self.assertEqual(filters.parse_salary("Competitive"), (None, None))

    def test_location(self):
        self.assertTrue(filters.location_ok({"remote": True, "location": "USA Only"}, CFG))
        self.assertFalse(filters.location_ok({"remote": True, "location": "Europe"}, CFG))
        self.assertTrue(filters.location_ok({"remote": False, "lat": 41.33, "lon": -93.10}, CFG))  # Knoxville
        self.assertFalse(filters.location_ok({"remote": False, "lat": 41.98, "lon": -91.67}, CFG))  # Cedar Rapids
        self.assertTrue(filters.location_ok({"remote": False, "location": "Oskaloosa, IA"}, CFG))
        self.assertFalse(filters.location_ok({"remote": False, "location": "Newton, MA"}, CFG))


class StoreTests(unittest.TestCase):
    def test_refresh_keeps_status_and_old_jobs(self):
        db = memdb()
        first = [j(title="Engineering Manager", location="Pella, IA")]
        refresh.run(db, CFG, {"fake": lambda cfg: first})
        job_id = store.list_jobs(db)[0]["id"]
        store.update_job(db, job_id, status="Applied", notes="Sent resume")

        second = [j(source_id="2", title="Plant Manager", location="Knoxville, IA"),
                  j(title="Engineering Manager", location="Pella, IA", salary_min=150000)]
        report = refresh.run(db, CFG, {"fake": lambda cfg: second})
        self.assertEqual((report["added"], report["seen"]), (1, 1))

        jobs = {x["title"]: x for x in store.list_jobs(db)}
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs["Engineering Manager"]["status"], "Applied")
        self.assertEqual(jobs["Engineering Manager"]["notes"], "Sent resume")
        self.assertEqual(jobs["Engineering Manager"]["salary_min"], 150000)

        refresh.run(db, CFG, {"fake": lambda cfg: []})
        self.assertEqual(len(store.list_jobs(db)), 2)

    def test_filters_applied_on_refresh(self):
        db = memdb()
        refresh.run(db, CFG, {"fake": lambda cfg: [
            j(title="Engineering Manager", location="Boston, MA"),
            j(title="Quality Director", location="Pella, IA", salary_max=90000),
            j(title="Receptionist", location="Pella, IA"),
        ]})
        self.assertEqual(store.list_jobs(db), [])

    def test_bad_status_rejected(self):
        with self.assertRaises(ValueError):
            store.update_job(memdb(), 1, status="Maybe")

    def test_failing_source_reported(self):
        def boom(cfg):
            raise OSError("network down")
        report = refresh.run(memdb(), CFG, {"fake": boom})
        self.assertEqual(report["sources"]["fake"], "error: network down")


class ConnectionTests(unittest.TestCase):
    def test_import_and_match(self):
        db = memdb()
        self.assertEqual(connections.replace_all(db, CONNECTIONS_CSV), 2)
        store.upsert_job(db, j(title="Engineering Manager", company="Vermeer"))
        store.upsert_job(db, j(title="Plant Manager", company="Acme"))
        store.upsert_job(db, j(title="Quality Manager", company="Pella Corporation"))
        found = {x["company"]: x["connections"] for x in store.list_jobs(db)}
        self.assertEqual([p["name"] for p in found["Vermeer"]], ["Jane Doe"])
        self.assertEqual(found["Vermeer"][0]["url"], "https://www.linkedin.com/in/janedoe")
        self.assertEqual(len(found["Acme"]), 1)
        self.assertEqual(found["Pella Corporation"], [])

    def test_reimport_replaces(self):
        db = memdb()
        connections.replace_all(db, CONNECTIONS_CSV)
        connections.replace_all(db, CONNECTIONS_CSV)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM connections").fetchone()[0], 2)

    def test_wrong_file(self):
        with self.assertRaises(ValueError):
            connections.parse("a,b,c\n1,2,3\n")


class SourceParseTests(unittest.TestCase):
    def test_remotive(self):
        out = remotive.parse({"jobs": [{"id": 5, "url": "https://r/5", "title": "AI Engineer",
                                        "company_name": "X", "candidate_required_location": "USA",
                                        "salary": "$140k-$170k", "publication_date": "2026-10-01T00:00:00"}]})
        self.assertEqual((out[0]["salary_min"], out[0]["salary_max"], out[0]["posted"]), (140000, 170000, "2026-10-01"))

    def test_remoteok(self):
        out = remoteok.parse([{"legal": "notice"}, {"id": "9", "position": "Staff Engineer", "company": "Y",
                                                     "salary_min": 150000, "salary_max": 0, "url": "u", "date": "2026-10-02T1"}])
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0]["salary_min"], out[0]["salary_max"]), (150000, None))

    def test_himalayas(self):
        out = himalayas.parse({"jobs": [{"title": "ML Engineer", "companyName": "Z", "minSalary": 130000,
                                         "maxSalary": 160000, "locationRestrictions": ["United States"],
                                         "applicationLink": "https://h/1", "guid": "g1", "pubDate": 1760000000}]})
        self.assertEqual(out[0]["location"], "United States")
        self.assertTrue(out[0]["posted"].startswith("2025"))

    def test_weworkremotely(self):
        xml = """<rss><channel><item><title>Acme: Director of Engineering</title><region>USA Only</region>
                 <link>https://wwr/1</link><guid>https://wwr/1</guid><pubDate>Mon, 13 Oct 2026 10:00:00 +0000</pubDate>
                 </item></channel></rss>"""
        out = weworkremotely.parse(xml)
        self.assertEqual((out[0]["company"], out[0]["title"], out[0]["posted"]), ("Acme", "Director of Engineering", "2026-10-13"))

    def test_adzuna(self):
        data = {"results": [{"id": "1", "title": "Quality Manager", "company": {"display_name": "Clow Valve"},
                             "location": {"display_name": "Oskaloosa, Mahaska County"}, "latitude": 41.29,
                             "longitude": -92.64, "salary_min": 100000, "salary_max": 100000,
                             "salary_is_predicted": "1", "redirect_url": "https://a/1", "created": "2026-10-10T00:00:00Z"}]}
        out = adzuna.parse(data)
        self.assertIsNone(out[0]["salary_min"])  # predicted salaries are ignored
        self.assertTrue(filters.location_ok(out[0], CFG))
        self.assertEqual(adzuna.parse(data, remote=True), [])  # not actually remote

    def test_usajobs(self):
        data = {"SearchResult": {"SearchResultItems": [{"MatchedObjectDescriptor": {
            "PositionID": "P1", "PositionTitle": "Supervisory Quality Manager", "OrganizationName": "VA",
            "PositionLocationDisplay": "Des Moines, Iowa", "PositionURI": "https://u/1",
            "PositionLocation": [{"Latitude": 41.59, "Longitude": -93.62}],
            "PositionRemuneration": [{"MinimumRange": "125000", "MaximumRange": "160000", "RateIntervalCode": "PA"}],
            "PublicationStartDate": "2026-10-01"}}]}}
        out = usajobs.parse(data)
        self.assertEqual((out[0]["salary_min"], out[0]["salary_max"]), (125000, 160000))

    def test_keyed_sources_skip_without_keys(self):
        cfg = dict(CFG, adzuna_app_id="", adzuna_app_key="", usajobs_api_key="", usajobs_email="")
        for mod in (adzuna, usajobs):
            with self.assertRaisesRegex(RuntimeError, "^skipped"):
                mod.fetch(cfg)


class ServerTests(unittest.TestCase):
    def test_api_round_trip(self):
        db = memdb()
        cfg = dict(CFG, port=0)
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(db, cfg))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        def call(path, body=None):
            data = body.encode() if isinstance(body, str) else (json.dumps(body).encode() if body is not None else None)
            with urllib.request.urlopen(urllib.request.Request(base + path, data=data)) as r:
                return r.read()

        try:
            self.assertIn(b"Job Search", call("/"))
            call("/api/jobs", {"title": "Engineering Manager", "company": "Vermeer", "location": "Pella, IA"})
            call("/api/connections", CONNECTIONS_CSV)
            state = json.loads(call("/api/jobs"))
            self.assertEqual(state["connection_count"], 2)
            jid = state["jobs"][0]["id"]
            self.assertEqual(state["jobs"][0]["connections"][0]["name"], "Jane Doe")
            call(f"/api/jobs/{jid}", {"status": "Applied"})
            self.assertEqual(json.loads(call("/api/jobs"))["jobs"][0]["status"], "Applied")
        finally:
            httpd.shutdown()


if __name__ == "__main__":
    unittest.main()


class ExportTests(unittest.TestCase):
    def test_export_merges_and_new_docs(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "jobs.json"
            r1 = refresh.export(path, CFG, {"fake": lambda cfg: [j(title="Engineering Manager", location="Pella, IA")]})
            r2 = refresh.export(path, CFG, {"fake": lambda cfg: [
                j(title="Engineering Manager", location="Pella, IA"),
                j(source_id="2", title="Plant Manager", location="Knoxville, IA"),
                j(source_id="3", title="Cashier", location="Pella, IA")]})
            self.assertEqual((r1["added"], r2["added"], r2["seen"]), (1, 1, 1))
            data = json.loads(path.read_text())
            self.assertEqual(len(data["jobs"]), 2)
            first_id = [x["id"] for x in data["jobs"] if x["title"] == "Engineering Manager"][0]
            written = refresh.new_docs(path, {first_id}, Path(d) / "docs")
            self.assertEqual(len(written), 1)
            doc = json.loads((Path(d) / "docs" / f"{written[0]}.json").read_text())
            self.assertEqual((doc["title"], doc["status"]), ("Plant Manager", "New"))


class GoogleJobsTests(unittest.TestCase):
    def test_parse_prefers_linkedin_indeed_glassdoor(self):
        from jobsearch.sources import googlejobs
        data = {"jobs_results": [
            {"title": "Quality Director", "company_name": "Vermeer", "location": "Pella, IA", "job_id": "x1",
             "via": "via LinkedIn", "detected_extensions": {"salary": "$130K–$160K a year"},
             "apply_options": [{"title": "Vermeer Careers", "link": "https://careers/1"},
                               {"title": "Indeed", "link": "https://indeed/1"}]},
            {"title": "AI Engineer", "company_name": "X", "location": "Anywhere", "job_id": "x2",
             "detected_extensions": {"work_from_home": True, "salary": "$60–$80 an hour"},
             "apply_options": [{"title": "LinkedIn", "link": "https://linkedin/2"}]},
        ]}
        a, b = googlejobs.parse(data)
        self.assertEqual((a["url"], a["source"], a["salary_min"], a["salary_max"]), ("https://indeed/1", "Indeed", 130000, 160000))
        self.assertEqual((b["source"], b["remote"], b["salary_min"]), ("LinkedIn", True, None))

    def test_skips_without_key(self):
        from jobsearch.sources import googlejobs
        with self.assertRaisesRegex(RuntimeError, "^skipped"):
            googlejobs.fetch(dict(CFG, serpapi_key=""))


class GoogleJobsRetryTests(unittest.TestCase):
    def test_one_timeout_keeps_other_results(self):
        from unittest import mock
        from jobsearch.sources import googlejobs
        calls = {"n": 0}

        def fake(url, params=None, headers=None, timeout=30):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise TimeoutError("The read operation timed out")
            return {"jobs_results": [{"title": "Plant Manager", "company_name": "C" + str(calls["n"]),
                                      "location": "Pella, IA", "apply_options": [{"title": "Indeed", "link": "u"}]}]}
        cfg = dict(CFG, serpapi_key="k", google_jobs_queries=["a", "b"])
        with mock.patch.object(googlejobs, "get_json", fake):
            jobs = googlejobs.fetch(cfg)
        self.assertEqual(len(jobs), 3)  # first search failed twice, the other three returned

    def test_all_failing_raises(self):
        from unittest import mock
        from jobsearch.sources import googlejobs
        with mock.patch.object(googlejobs, "get_json", side_effect=TimeoutError("timed out")):
            with self.assertRaisesRegex(RuntimeError, "all Google Jobs searches failed"):
                googlejobs.fetch(dict(CFG, serpapi_key="k", google_jobs_queries=["a"]))
