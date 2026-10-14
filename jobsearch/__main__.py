"""Usage:
  python -m jobsearch                      open the job list in your browser
  python -m jobsearch refresh              pull new postings without opening the page
  python -m jobsearch connections FILE     import LinkedIn Connections.csv
  python -m jobsearch export FILE          refresh into a JSON file (feeds the website)
  python -m jobsearch new-docs FILE IDS DIR write website docs for jobs not listed in IDS (one id per line)
"""

import sys
from pathlib import Path

from . import config, connections, refresh, server, store


def main(argv):
    cfg = config.load()
    cmd = argv[0] if argv else "serve"
    db = None if cmd in ("export", "new-docs") else store.connect()
    if cmd == "serve":
        server.serve(db, cfg, open_browser="--no-browser" not in argv)
    elif cmd == "refresh":
        report = refresh.run(db, cfg)
        print(f"{report['added']} new, {report['seen']} already saved")
        for name, result in report["sources"].items():
            print(f"  {name}: {result}")
    elif cmd == "connections" and len(argv) > 1:
        n = connections.replace_all(db, Path(argv[1]).read_text(encoding="utf-8-sig"))
        print(f"Imported {n} connections")
    elif cmd == "export" and len(argv) > 1:
        report = refresh.export(argv[1], cfg)
        print(f"{report['added']} new, {report['seen']} already saved")
        for name, result in report["sources"].items():
            print(f"  {name}: {result}")
    elif cmd == "new-docs" and len(argv) > 3:
        ids_file = Path(argv[2])
        existing = set(ids_file.read_text().split()) if ids_file.exists() else set()
        written = refresh.new_docs(argv[1], existing, argv[3])
        print(f"{len(written)} new jobs written to {argv[3]}")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
