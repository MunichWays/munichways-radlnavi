"""Inspect the current exported Lua tag resolver; this is no OSRM integration test.

Run with backend/.venv/Scripts/python.exe (requires lupa==2.6).
Only unused lib/* imports are stubbed; the resolver is loaded from bike.lua.
"""

import hashlib
import json
from pathlib import Path
import subprocess

from lupa import LuaRuntime


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASELINE_COMMIT = "0aeead62ea82aa599a77eac7f274e3711f095536"


def main():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().package.path = str(REPO / "routing" / "?.lua").replace("\\", "/") + ";" + lua.globals().package.path
    lua.execute("""
        package.preload['lib/set'] = function() return function(v) return v end end
        package.preload['lib/sequence'] = function() return function(v) return v end end
        package.preload['lib/way_handlers'] = function() return {} end
        package.preload['lib/access'] = function()
            return {find_access_tag=function() end}
        end
        package.preload['lib/maxspeed'] = function()
            return {limit=function() end}
        end
    """)
    source = subprocess.check_output(
        ["git", "show", f"{BASELINE_COMMIT}:routing/bike.lua"], cwd=REPO
    )
    profile = lua.execute(source.decode("utf-8"))
    make_way = lua.eval("""function(tags)
        return {get_value_by_key=function(self,key) return tags[key] end}
    end""")
    data = json.loads((ROOT / "munich-side-tags.json").read_text(encoding="utf-8"))
    rows = []
    for item in data["elements"]:
        if item["type"] != "way":
            continue
        way = make_way(lua.table_from(item["tags"]))
        rows.append({
            "way_id": item["id"],
            "surface": profile.get_cycling_tag(way, "surface"),
            "smoothness": profile.get_cycling_tag(way, "smoothness"),
        })
    output = {
        "method": "Actual exported bike.lua get_cycling_tag via lupa 2.6; unused lib/* dependencies stubbed; no process_way or OSRM integration run",
        "commit": BASELINE_COMMIT,
        "bike_lua_sha256": hashlib.sha256(source).hexdigest(),
        "resolved_attributes": rows,
    }
    (ROOT / "baseline-resolver.json").write_text(
        json.dumps(output, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Inspected current Lua resolver on {len(rows)} OSM ways")


if __name__ == "__main__":
    main()
