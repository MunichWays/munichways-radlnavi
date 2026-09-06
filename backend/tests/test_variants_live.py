"""Integration checks against the isolated fixture API (no production requests)."""

import argparse
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def fetch(base, path, body=None):
    request = Request(
        base + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def check(base):
    capabilities = fetch(base, "/routing_variants")
    assert capabilities["direct"]["available"]
    results = {}
    for variant, index in (("standard", 100), ("direct", 35)):
        for coordinates, leg_count in (
            ("11,48.6;11.002,48.6", 1),
            ("11,48.6;11.001,48.6;11.002,48.6;11,48.6", 3),
        ):
            query = urlencode(
                dict(
                    variant=variant,
                    steps="true",
                    annotations="nodes,distance",
                    geometries="geojson",
                    overview="full",
                    comfort="true",
                )
            )
            payload = fetch(base, f"/route/v1/bike/{coordinates}?{query}")
            assert payload["code"] == "Ok"
            route = payload["routes"][0]
            assert len(route["legs"]) == leg_count
            assert route["geometry"]["type"] == "LineString"
            assert route["comfortAnalysis"]["distanceComplete"]
            assert all(
                leg["steps"][-1]["maneuver"]["type"] == "arrive"
                for leg in route["legs"]
            )
            if leg_count == 1:
                assert route["comfort"]["index"] == index
                results[variant] = {
                    key: route[key] for key in ("distance", "duration", "comfort")
                }
            # Check independent post-route analysis, including all waypoint legs.
            legs = [
                {
                    "nodes": leg["annotation"]["nodes"],
                    "distance": leg["annotation"]["distance"],
                    "start": payload["waypoints"][i]["location"],
                    "end": payload["waypoints"][i + 1]["location"],
                }
                for i, leg in enumerate(route["legs"])
            ]
            analysis = fetch(
                base, "/tag_distribution", {"variant": variant, "legs": legs}
            )
            assert analysis["comfort"] == route["comfort"]
    assert results["direct"]["distance"] < results["standard"]["distance"]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18090")
    check(parser.parse_args().base_url)
