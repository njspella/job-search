"""Usage:
  python -m jobsearch                      open the job list in your browser
  python -m jobsearch refresh              pull new postings without opening the page
  python -m jobsearch connections FILE     import LinkedIn Connections.csv
"""

import sys
from pathlib import Path

from . import config, connections, refresh, server, store


def main(argv):
    cfg = config.load()
    db = store.connect()
    cmd = argv[0] if argv else "serve"
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
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
