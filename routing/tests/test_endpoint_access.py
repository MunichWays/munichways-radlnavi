"""Full backend endpoint composition against unchanged real OSRM bike graphs.

Requires osmium for the same database import used by the deployed backend.
"""

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from src.endpoint_routes import endpoint_route
from src.geo_store import __initialize_geo_store


FIXTURE = Path(__file__).with_name("fixtures") / "munich-endpoint-access.osm"
CASES = (
    ("Hofgarten A", "11.579101,48.143125;11.578120,48.142766", 100, 120),
    ("Hofgarten B", "11.578351,48.142871;11.578114,48.142715", 95, 115),
    ("Botanischer Garten", "11.563519,48.141857;11.565723,48.143933", 310, 350),
)


def fetcher(endpoint):
    def fetch(coordinates, query):
        url = f"{endpoint}/route/v1/bike/{coordinates}?{urllib.parse.urlencode(query)}"
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                status, payload = response.status, json.load(response)
        except urllib.error.HTTPError as error:
            status, payload = error.code, json.load(error)
        return SimpleNamespace(status_code=status, json=lambda:payload)
    return fetch


def validate(payload, minimum, maximum):
    route = payload["routes"][0]
    assert minimum < route["distance"] < maximum, route
    assert len(route["legs"]) == len(payload["waypoints"]) - 1
    geometry = route["geometry"]["coordinates"]
    step_geometry = []
    for index, leg in enumerate(route["legs"]):
        annotation = leg["annotation"]
        assert len(annotation["nodes"]) == len(annotation["distance"]) + 1
        assert abs(sum(annotation["distance"]) - leg["distance"]) < 0.2
        assert leg["steps"][-1]["maneuver"]["type"] == "arrive"
        for step in leg["steps"]:
            if step["maneuver"]["type"] == "arrive": continue
            for point in step["geometry"]["coordinates"]:
                if not step_geometry or point != step_geometry[-1]:
                    step_geometry.append(point)
    assert geometry == step_geometry, "Mode sections must match full geometry exactly"
    return route


def check(db, endpoint, variant):
    fetch = fetcher(endpoint)
    params = [("geometries", "geojson"), ("overview", "full"),
              ("steps", "true"), ("annotations", "true"), ("alternatives", "false")]
    for name, coordinates, minimum, maximum in CASES:
        for reverse, text in enumerate((coordinates, ";".join(reversed(coordinates.split(";"))))):
            baseline = fetch(text, params).json()
            result = endpoint_route(db, "bike", text, params, baseline, fetch, variant)
            assert result is not None, (name, variant, text)
            # The cycling road next to the Hofgarten is directional; the
            # reverse journey legitimately uses the other nearby exit.
            lower, upper = minimum, maximum
            if reverse:
                lower, upper = {"Hofgarten B": (60, 85),
                    "Botanischer Garten": (350, 390)}.get(name, (minimum, maximum))
            route = validate(result, lower, upper)
            steps = [s for leg in route["legs"] for s in leg["steps"] if s["distance"] > 0]
            assert any(s["mode"] == "pushing bike" for s in steps)
            assert max(w["distance"] for w in result["waypoints"]) < 10
            if name == "Hofgarten A":
                assert all(s["mode"] == "pushing bike" for s in steps)
            else:
                assert any(s["mode"] == "cycling" for s in steps)
            print(variant, name, text, round(route["distance"], 1), "m")

    # Between cycling endpoints the entire response/weight model is unchanged,
    # even when the rejected pedestrian connection would shorten the journey.
    coordinates = "11.563063,48.1415279;11.5642517,48.1426711"
    baseline = fetch(coordinates, params).json()
    assert baseline["code"] == "Ok"
    assert endpoint_route(db, "bike", coordinates, params, baseline, fetch, variant) is None

    # The old cycling portion remains an independent OSRM request, including
    # mandatory intermediate waypoints and their leg/annotation boundaries.
    text = "11.563519,48.141857;11.5647,48.1427;11.565723,48.143933"
    baseline = fetch(text, params).json()
    result = endpoint_route(db, "bike", text, params, baseline, fetch, variant)
    assert result is not None
    route = validate(result, 300, 1200)
    assert len(route["legs"]) == 2 and len(result["waypoints"]) == 3
    assert result["waypoints"][1] == baseline["waypoints"][1]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--standard", default="http://127.0.0.1:18085")
    parser.add_argument("--direct", default="http://127.0.0.1:18086")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as folder, closing(sqlite3.connect(Path(folder) / "geo.db")) as db:
        __initialize_geo_store(db, str(FIXTURE))
        check(db, args.standard, "standard")
        check(db, args.direct, "direct")
    print("Endpoint access and unchanged bicycle routing passed")
