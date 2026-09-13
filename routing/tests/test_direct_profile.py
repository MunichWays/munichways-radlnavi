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
    assert direct["weight_name"] == "fast_cycling", direct
    # Direct selects physical travel time. The shorter grass-paver shortcut is
    # slower under the shared speed model and must therefore lose.
    assert direct["duration"] < direct["distance"] / (6 / 3.6), direct
    assert abs(direct["weight"] - direct["duration"]) < 0.5, direct
    for route, name in ((standard, "Comfortable detour"), (direct, "Comfortable detour")):
        assert any(
            step.get("name") == name for step in route["legs"][0]["steps"]
        ), route
        assert route["geometry"]["type"] == "LineString", route
        assert route["legs"][0]["steps"][-1]["maneuver"]["type"] == "arrive", route

    with_stops = "11.0000,48.6000;11.0010,48.6000;11.0020,48.6000;11.0000,48.6000"
    # Both variants exclude ferries, with or without a fixed duration.
    for endpoint in (args.standard, args.direct):
        for coordinates in (
            "10.9990,48.6100;11.0030,48.6100",
            "11.0030,48.6100;10.9990,48.6100",
            "11.0000,48.6300;11.0010,48.6300",
            "11.0010,48.6300;11.0000,48.6300",
        ):
            result = fetch(endpoint, coordinates)
            assert result["code"] in ("NoRoute", "NoSegment"), result
    # Both variants prefer a rideable detour but retain stairs as a last resort.
    for coordinates in (
        "11.0000,48.6400;11.0010,48.6400",
        "11.0010,48.6400;11.0000,48.6400",
    ):
        for endpoint in (args.standard, args.direct):
            detour = successful(endpoint, coordinates)
            names = [step.get("name") for step in detour["legs"][0]["steps"]]
            assert "Rideable detour" in names and "Stair shortcut" not in names, detour
    for lat in (48.6200, 48.6500):
        for coordinates in (
            f"11.0000,{lat:.4f};11.0010,{lat:.4f}",
            f"11.0010,{lat:.4f};11.0000,{lat:.4f}",
        ):
            durations = []
            for endpoint in (args.standard, args.direct):
                stairs = successful(endpoint, coordinates)
                durations.append(stairs["duration"])
                assert abs(stairs["duration"] - stairs["distance"] * 1.8) < 2, stairs
                if endpoint == args.direct:
                    assert abs(stairs["weight"] - stairs["distance"] * 3.6) < 2, stairs
            assert durations[0] == durations[1], durations
    for endpoint in (args.standard, args.direct):
        result = fetch(endpoint, "11.0000,48.6600;11.0010,48.6600")
        assert result["code"] in ("NoRoute", "NoSegment"), result

    # A comfort rating is never an access rule for Direct. Identical asphalt
    # ways get identical Direct time and weight regardless of class:bicycle.
    class_minus_three = successful(args.direct, "11.0000,48.6700;11.0010,48.6700")
    class_plus_three = successful(args.direct, "11.0000,48.6800;11.0010,48.6800")
    assert abs(class_minus_three["duration"] - class_plus_three["duration"]) < 0.5
    assert abs(class_minus_three["weight"] - class_plus_three["weight"]) < 0.5
    blocked_standard = fetch(args.standard, "11.0000,48.6700;11.0010,48.6700")
    assert blocked_standard["code"] in ("NoRoute", "NoSegment"), blocked_standard
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
    for endpoint in (args.standard, args.direct):
        # No implicit pushing fallback against a cycling one-way, including
        # explicit dismount and the shared path seen at Lenbachplatz.
        for lat in (48.7000, 48.7400, 48.7500, 48.7600):
            successful(endpoint, f"11.0000,{lat:.4f};11.0010,{lat:.4f}")
            blocked = fetch(endpoint, f"11.0010,{lat:.4f};11.0000,{lat:.4f}")
            assert blocked["code"] in ("NoRoute", "NoSegment"), blocked
        successful(endpoint, "11.0010,48.7100;11.0000,48.7100")
        blocked = fetch(endpoint, "11.0000,48.7100;11.0010,48.7100")
        assert blocked["code"] in ("NoRoute", "NoSegment"), blocked
        # Explicit bicycle counterflow remains cycling, not pushing.
        for lat in (48.7200, 48.7300):
            counterflow = successful(endpoint, f"11.0010,{lat:.4f};11.0000,{lat:.4f}")
            assert all(
                step["mode"] == "cycling" for step in counterflow["legs"][0]["steps"]
            )
        # Ordinary dismount connections remain usable for both variants.
        for coordinates in ("11,48.77;11.001,48.77", "11.001,48.77;11,48.77"):
            pushing = successful(endpoint, coordinates)
            assert abs(pushing["duration"] - pushing["distance"] * 0.9) < 2, pushing
            if endpoint == args.direct:
                assert abs(pushing["weight"] - pushing["distance"] * 1.8) < 2, pushing
        preferences = ((48.78, "Cycling detour"), (48.80, "Push shortcut"))
        for lat, preferred in preferences:
            for coordinates in (f"11,{lat};11.001,{lat}", f"11.001,{lat};11,{lat}"):
                choice = successful(endpoint, coordinates)
                names = [step.get("name") for step in choice["legs"][0]["steps"]]
                assert preferred in names, (preferred, choice)
    restricted = successful(args.direct, "11.0000,48.4200;11.0005,48.4205")
    excepted = successful(args.direct, "11.0000,48.4300;11.0005,48.4305")
    assert restricted["distance"] > 150, restricted
    assert excepted["distance"] < 100, excepted
    sidepath = fetch(args.direct, "11.0005,48.4495;11.0005,48.4505")
    assert sidepath["code"] in ("NoRoute", "NoSegment"), sidepath

    # Signal delay remains in ETA but contributes only 25 percent to the Direct
    # search weight. A single signal adds six seconds to travel time.
    direct_without_signal = successful(args.direct, "11,48.30;11.001,48.30")
    direct_with_signal = successful(args.direct, "11,48.31;11.001,48.31")
    assert abs(
        (direct_with_signal["duration"] - direct_without_signal["duration"]) - 6
    ) < 0.3
    assert abs(
        (direct_with_signal["weight"] - direct_without_signal["weight"]) - 1.5
    ) < 0.3
    # A railway crossing uses the stop obstacle and must not receive the discount.
    crossing = successful(args.direct, "11,48.41;11.001,48.41")
    assert abs(crossing["weight"] - direct_without_signal["weight"] - 6) < 0.3, crossing
    assert abs(crossing["duration"] - direct_without_signal["duration"] - 6) < 0.3
    # Physical travel time stays identical on the same geometry: roads, rough
    # surfaces, signals, level crossings, turns, stairs and dismount connections.
    for coordinates in (
        "11,48.60;11.002,48.60", "11,48.06;11.001,48.06",
        "11,48.31;11.001,48.31", "11,48.41;11.001,48.41",
        "11,48.39;11.0005,48.3905", "11,48.77;11.001,48.77",
        "11,48.86;11.002,48.86", "11,48.88;11.002,48.88",
    ):
        a = successful(args.standard, coordinates)
        b = successful(args.direct, coordinates)
        assert a["geometry"] == b["geometry"], coordinates
        assert a["duration"] == b["duration"], (coordinates, a, b)
    # A small residential penalty can break a near tie, but must not force a
    # large detour. Verify both directions, not just the numeric profile values.
    for start, end in ((11, 11.002), (11.002, 11)):
        near_tie = successful(args.direct, f"{start},48.82;{end},48.82")
        names = [step.get("name") for step in near_tie["legs"][0]["steps"]]
        assert "Main connection" in names, near_tie
        shorter = successful(args.direct, f"{start},48.84;{end},48.84")
        names = [step.get("name") for step in shorter["legs"][0]["steps"]]
        assert "Useful residential connection" in names, shorter
        assert "Excessive main-road detour" not in names, shorter
    # Surface selection penalties do not fabricate slower displayed cycling
    # speeds; fine gravel receives a much smaller penalty than coarse gravel.
    for coordinates, factor in (
        ("11,48;11.001,48", 1.08),
        ("11,48.86;11.002,48.86", 1.25),
        ("11,48.88;11.002,48.88", 1.05),
    ):
        route = successful(args.direct, coordinates)
        assert abs(route["weight"] - route["duration"] * factor) < 0.4, route
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
        "Direct profile: fast-cycling, navigation, intermediate stops and access checks passed"
    )


if __name__ == "__main__":
    main()
