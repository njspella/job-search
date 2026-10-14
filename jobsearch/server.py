"""Local web page for browsing jobs. Listens on 127.0.0.1 only, so it is private to your computer."""

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import connections, refresh, store

WEB = Path(__file__).resolve().parent / "web"


def make_handler(db, cfg):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def body(self):
            n = int(self.headers.get("Content-Length") or 0)
            return self.rfile.read(n).decode("utf-8", errors="replace") if n else ""

        def state(self):
            count = db.execute("SELECT COUNT(*) FROM connections").fetchone()[0]
            return {"jobs": store.list_jobs(db), "statuses": store.STATUSES,
                    "last_refresh": store.last_refresh(db), "connection_count": count}

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                return self.send(200, (WEB / "index.html").read_bytes(), "text/html; charset=utf-8")
            if self.path == "/api/jobs":
                with lock:
                    return self.send(200, self.state())
            self.send(404, {"error": "not found"})

        def do_POST(self):
            try:
                with lock:
                    if self.path == "/api/refresh":
                        report = refresh.run(db, cfg)
                        return self.send(200, {"report": report, **self.state()})
                    if self.path == "/api/connections":
                        n = connections.replace_all(db, self.body())
                        return self.send(200, {"imported": n, **self.state()})
                    if self.path == "/api/jobs":
                        j = json.loads(self.body() or "{}")
                        if not (j.get("title") and j.get("company")):
                            return self.send(400, {"error": "title and company are required"})
                        j["source"] = "manual"
                        store.upsert_job(db, j)
                        db.commit()
                        return self.send(200, self.state())
                    m = re.fullmatch(r"/api/jobs/(\d+)", self.path)
                    if m:
                        j = json.loads(self.body() or "{}")
                        store.update_job(db, int(m.group(1)), j.get("status"), j.get("notes"))
                        return self.send(200, {"ok": True})
                self.send(404, {"error": "not found"})
            except ValueError as e:
                self.send(400, {"error": str(e)})

    return Handler


def serve(db, cfg, open_browser=True):
    port = cfg["port"]
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(db, cfg))
    url = f"http://127.0.0.1:{port}/"
    print(f"Job search is running at {url}  (Ctrl+C to stop)")
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
