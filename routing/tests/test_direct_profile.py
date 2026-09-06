"""Exercise both real OSRM profiles built from profile-fixture.osm."""

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request


def fetch(endpoint, coordinates):
    query = urllib.parse.urlencode(
        {
            "steps": "true",
            "overview": "full",
            "geometries": "geojson",
            "annotations": "nodes,distance",
            "alternatives": "false",
            "radiuses": ";".join("8" for _ in coordinates.split(";")),
        }
    )
    try:
        with urllib.request.urlopen(
            f"{endpoint}/route/v1/bike/{coordinates}?{query}", timeout=10
        ) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        return json.load(error)


def successful(endpoint, coordinates):
    result = fetch(endpoint, coordinates)
    assert result["code"] == "Ok", result
    return result["routes"][0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--standard", default="http://localhost:18081")
    parser.add_argument("--direct", default="http://localhost:18082")
    args = parser.parse_args()
    coordinates = "11.0000,48.6000;11.0020,48.6000"
    standard = successful(args.standard, coordinates)
    direct = successful(args.direct, coordinates)
    assert standard["weight_name"] == "cyclability", standard
    assert direct["weight_name"] == "distance", direct
    assert direct["distance"] < standard["distance"] * 0.7, (standard, direct)
    # Shortest must not silently become fastest: the rough shortcut is slower.
    assert direct["duration"] > standard["duration"], (standard, direct)
    assert abs(direct["weight"] - direct["distance"]) < 0.5, direct
    for route, name in ((standard, "Comfortable detour"), (direct, "Short rough road")):
        assert any(
            step.get("name") == name for step in route["legs"][0]["steps"]
        ), route
        assert route["geometry"]["type"] == "LineString", route
        assert route["legs"][0]["steps"][-1]["maneuver"]["type"] == "arrive", route

    with_stops = "11.0000,48.6000;11.0010,48.6000;11.0020,48.6000;11.0000,48.6000"
    ferry = successful(args.direct, "10.9990,48.6100;11.0030,48.6100")
    assert abs(ferry["weight"] - ferry["distance"]) < 0.5, ferry
    assert 300 < ferry["duration"] < 400, ferry
    assert any(step["mode"] == "ferry" for step in ferry["legs"][0]["steps"]), ferry
    for endpoint in (args.standard, args.direct):
        route = successful(endpoint, with_stops)
        assert len(route["legs"]) == 3, route
        for leg in route["legs"]:
            assert leg["steps"][-1]["maneuver"]["type"] == "arrive", leg
            assert (
                len(leg["annotation"]["distance"])
                == len(leg["annotation"]["nodes"]) - 1
            ), leg
        refreshed = successful(endpoint, "11.0010,48.6000;11.0020,48.6000")
        assert refreshed["legs"][0]["steps"], refreshed

    # Retain explicit exclusions, bicycle access, stairs and barrier behavior.
    for lat in (48.1100, 48.2000, 48.2100, 48.2200, 48.2600, 48.2700):
        result = fetch(args.direct, f"11.0000,{lat:.4f};11.0010,{lat:.4f}")
        assert result["code"] in ("NoRoute", "NoSegment"), (lat, result)
    successful(args.direct, "11.0010,48.4400;11.0000,48.4400")
    restricted = successful(args.direct, "11.0000,48.4200;11.0005,48.4205")
    excepted = successful(args.direct, "11.0000,48.4300;11.0005,48.4305")
    assert restricted["distance"] > 150, restricted
    assert excepted["distance"] < 100, excepted
    sidepath = fetch(args.direct, "11.0005,48.4495;11.0005,48.4505")
    assert sidepath["code"] in ("NoRoute", "NoSegment"), sidepath
    print(
        json.dumps(
            {
                "standard_distance": standard["distance"],
                "direct_distance": direct["distance"],
                "standard_duration": standard["duration"],
                "direct_duration": direct["duration"],
            }
        )
    )
    print(
        "Direct profile: navigation, intermediate stops, refresh, access and shortest-distance checks passed"
    )


if __name__ == "__main__":
    main()
