"""Local benchmark worker using a disposable database; never a deployment entrypoint."""

import argparse
import os
from pathlib import Path
import sqlite3
import sys

os.environ.setdefault("OSRM_BACKEND_URL", "http://unused.invalid")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import app
import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--port", type=int, default=18090)
    args = parser.parse_args()
    uri = Path(args.database).resolve().as_uri() + "?mode=ro"
    app.get_geo_store = lambda: sqlite3.connect(uri, uri=True)
    uvicorn.run(app.app, host="0.0.0.0", port=args.port, access_log=False)
