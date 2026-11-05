"""Real OSRM checks: relaxed detour, unchanged access, stops and recovery."""
import argparse
from test_direct_profile import fetch, successful


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--standard", default="http://localhost:18081")
    parser.add_argument("--discovery", default="http://localhost:18091")
    args = parser.parse_args()
    coordinates = "11,49.4;11.002,49.4"
    standard = successful(args.standard, coordinates)
    discovery = successful(args.discovery, coordinates)
    names = lambda route: [step.get("name") for leg in route["legs"] for step in leg["steps"]]
    assert "Standard street" in names(standard), standard
    assert "Discovery green detour" in names(discovery), discovery
    assert discovery["distance"] > standard["distance"], (standard, discovery)
    assert discovery["weight_name"] == "relaxed_cycling"
    for lat in (48.1100, 48.2000, 48.2100, 48.2200, 48.6700):
        response = fetch(args.discovery, f"11,{lat};11.001,{lat}")
        assert response["code"] in ("NoRoute", "NoSegment"), response
    for lat in (48.7000, 48.7400, 48.7500, 48.7600):
        response = fetch(args.discovery, f"11.001,{lat};11,{lat}")
        assert response["code"] in ("NoRoute", "NoSegment"), response
    route = successful(args.discovery, "11,49.4;11.001,49.4005;11.002,49.4;11,49.4")
    assert len(route["legs"]) == 3, route
    for leg in route["legs"]:
        assert leg["steps"][-1]["maneuver"]["type"] == "arrive"
        assert len(leg["annotation"]["nodes"]) == len(leg["annotation"]["distance"]) + 1
    successful(args.discovery, coordinates)  # usable again after rejected routes
    print("Discovery detour, access, navigation, stops and recovery OK")


if __name__ == "__main__":
    main()
