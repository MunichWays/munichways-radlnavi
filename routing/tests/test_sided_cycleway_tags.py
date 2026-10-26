"""Check directional speeds, weights, access and real Munich ways in OSRM."""

import argparse
import json
import math
from pathlib import Path

from test_direct_profile import fetch, successful


def check(standard, direct):
    cases = json.loads((Path(__file__).parent / "cycling-attribute-cases.json").read_text())
    for index, case in enumerate(cases):
        if "profile" not in case:
            continue
        forward_speed, backward_speed, forward_cost, backward_cost = case["profile"]
        lat = 50 + index / 100
        for start, end, speed, cost in (
            (11, 11.001, forward_speed, forward_cost),
            (11.001, 11, backward_speed, backward_cost),
        ):
            coordinates = f"{start},{lat:.4f};{end},{lat:.4f}"
            routes = [successful(endpoint, coordinates) for endpoint in (standard, direct)]
            for route in routes:
                assert math.isclose(route["duration"], route["distance"] / (speed / 3.6), abs_tol=0.2), (case["id"], coordinates, route)
            assert routes[0]["duration"] == routes[1]["duration"], case["id"]
            assert routes[0]["geometry"] == routes[1]["geometry"], case["id"]
            standard_cost = case.get("standard_cost", {}).get("forward" if start == 11 else "backward", 1)
            assert math.isclose(routes[0]["weight"], routes[0]["duration"] * standard_cost, abs_tol=0.3), (case["id"], routes[0])
            assert math.isclose(routes[1]["weight"], routes[1]["duration"] * cost * 1.08, abs_tol=0.3), (case["id"], routes[1])

    # Original Gerner Straße: no signals or maneuvers within this subsegment.
    a, b = "11.5237591,48.1615315", "11.5243873,48.1607003"
    for coordinates, speed, cost in ((f"{a};{b}", 14, 1), (f"{b};{a}", 6.3, 1.15)):
        routes = [successful(endpoint, coordinates) for endpoint in (standard, direct)]
        for route in routes:
            assert math.isclose(route["duration"], route["distance"] / (speed / 3.6), abs_tol=0.2), route
        assert math.isclose(routes[0]["weight"], routes[0]["duration"] / 0.45, abs_tol=0.3), routes[0]
        assert math.isclose(routes[1]["weight"], routes[1]["duration"] * cost * 1.08, abs_tol=0.3), routes[1]

    # The sided surface resolver cannot open Sarasatestraße's forbidden reverse.
    for endpoint in (standard, direct):
        result = fetch(endpoint, "11.4777800,48.1621749;11.4767071,48.1622325")
        assert result["code"] in {"NoRoute", "NoSegment"}, result
        for coordinates, expected in (
            ("11,50.4;11.002,50.4", "Directional shortcut"),
            ("11.002,50.4;11,50.4", "Paved detour"),
        ):
            route = successful(endpoint, coordinates)
            names = [step.get("name") for leg in route["legs"] for step in leg["steps"]]
            assert expected in names, (coordinates, expected, route)
    print("Directional cycling attributes: speeds, weights, original Gerner Straße and one-way protection passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--standard", default="http://localhost:18089")
    parser.add_argument("--direct", default="http://localhost:18090")
    args = parser.parse_args()
    check(args.standard, args.direct)
