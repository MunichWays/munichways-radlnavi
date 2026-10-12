"""Check cycleway surface/smoothness precedence through both real OSRM profiles."""

import argparse
import math

from test_direct_profile import successful


def check(standard, direct):
    # latitude, physical speed in km/h, Direct surface cost. These isolated
    # cycleways have no turns, signals or residential-road selection costs.
    cases = (
        (49.00, 20, 1),  # no surface or smoothness tags
        (49.01, 6.3, 1.15),  # general sett + bad remain the fallback
        (49.02, 20, 1),  # cycleway asphalt overrides general sett
        (49.03, 9, 1.15),  # cycleway sett overrides general asphalt
        (49.04, 20, 1),  # cycleway excellent overrides general bad
        (49.05, 18, 1),  # cycleway intermediate overrides general excellent
        (49.06, 14, 1),  # only surface overridden; general bad still applies
        (49.07, 9, 1.15),  # only smoothness overridden; general sett still applies
        (49.08, 6, 1.25),  # cycleway surface works without general surface
        (49.09, 18, 1),  # Golo-Mann-Weg: only cycleway intermediate
        (49.10, 20, 1),  # Ludwigsbruecke: only cycleway excellent
        (49.11, 20, 1),  # unknown cycleway values still override general tags
        (49.12, 6.3, 1.15),  # both cycleway tags override independently
    )
    for lat, speed, surface_cost in cases:
        for start, end in ((11, 11.001), (11.001, 11)):
            coordinates = f"{start},{lat:.4f};{end},{lat:.4f}"
            routes = [successful(endpoint, coordinates) for endpoint in (standard, direct)]
            for route in routes:
                assert math.isclose(
                    route["duration"], route["distance"] / (speed / 3.6), abs_tol=0.2
                ), (coordinates, speed, route)
            assert routes[0]["geometry"] == routes[1]["geometry"], coordinates
            assert routes[0]["duration"] == routes[1]["duration"], coordinates
            # Standard retains its default class:bicycle factor of 0.55.
            assert math.isclose(
                routes[0]["weight"], routes[0]["duration"] / 0.55, abs_tol=0.3
            ), (coordinates, routes[0])
            assert math.isclose(
                routes[1]["weight"], routes[1]["duration"] * surface_cost, abs_tol=0.3
            ), (coordinates, surface_cost, routes[1])

    # Each pair has identical geometry and general tags. The cycleway-specific
    # tag alone changes whether the short connection beats the asphalt detour.
    for lat, preferred in (
        (49.20, "Asphalt detour"),
        (49.22, "Cycleway surface shortcut"),
        (49.24, "Asphalt detour"),
        (49.26, "Cycleway smoothness shortcut"),
    ):
        for start, end in ((11, 11.002), (11.002, 11)):
            for endpoint in (standard, direct):
                route = successful(endpoint, f"{start},{lat};{end},{lat}")
                names = [step.get("name") for step in route["legs"][0]["steps"]]
                assert preferred in names, (lat, endpoint, preferred, route)

    # Frozen original OSM ways: Ludwigsbruecke (23457803) and Golo-Mann-Weg
    # (513653294). Both are segregated foot/cycle paths with class:bicycle=2,
    # general surface=paved and no general smoothness. The detailed cycling
    # attributes apply without requiring an additional cycleway=* tag.
    for start, end, speed in (
        ("11.5849614,48.1322162", "11.5851406,48.1321141", 18),
        ("11.4089472,48.1426622", "11.4081195,48.1455993", 16.2),
    ):
        for coordinates in (f"{start};{end}", f"{end};{start}"):
            routes = [successful(endpoint, coordinates) for endpoint in (standard, direct)]
            for route in routes:
                assert math.isclose(
                    route["duration"], route["distance"] / (speed / 3.6), abs_tol=0.2
                ), (coordinates, speed, route)
                assert math.isclose(route["weight"], route["duration"], abs_tol=0.2), route
            assert routes[0]["geometry"] == routes[1]["geometry"], coordinates
            assert routes[0]["duration"] == routes[1]["duration"], coordinates


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--standard", default="http://localhost:18081")
    parser.add_argument("--direct", default="http://localhost:18082")
    args = parser.parse_args()
    check(args.standard, args.direct)
    print("Cycleway tag precedence, times, weights and route choices passed in both directions")
