#!/usr/bin/env python3
"""Check stable routing corridors against an OSRM-compatible endpoint."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_CASES = Path(__file__).with_name("route-regressions.json")


def step_names(route: dict[str, Any]) -> list[str]:
    return [
        step["name"]
        for step in route["legs"][0]["steps"]
        if step.get("name")
    ]


def is_ordered_subsequence(expected: list[str], actual: list[str]) -> bool:
    remaining = iter(actual)
    return all(any(name == candidate for candidate in remaining) for name in expected)


def fetch_route(
    endpoint: str, coordinates: str, attempts: int = 30
) -> dict[str, Any]:
    url = (
        f"{endpoint.rstrip('/')}/route/v1/bike/{coordinates}"
        "?steps=true&overview=false"
    )
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                return json.load(response)
        except (OSError, urllib.error.URLError):
            if attempt == attempts:
                raise
            if attempt == 1:
                print("Waiting for routing endpoint to become ready ...")
            time.sleep(2)

    raise AssertionError("unreachable")


def check_case(endpoint: str, case: dict[str, Any]) -> list[str]:
    response = fetch_route(endpoint, case["coordinates"])
    if response.get("code") != "Ok" or not response.get("routes"):
        return [f"OSRM returned {response.get('code', 'no code')!r}"]

    route = response["routes"][0]
    actual_names = step_names(route)
    expected_names = case["expected_step_names"]
    errors = []

    if not is_ordered_subsequence(expected_names, actual_names):
        errors.append(
            "street sequence changed: expected "
            f"{' -> '.join(expected_names)}, got {' -> '.join(actual_names)}"
        )

    distance = float(route["distance"])
    baseline = float(case["baseline_distance_m"])
    tolerance = float(case["distance_tolerance"])
    minimum = baseline * (1 - tolerance)
    maximum = baseline * (1 + tolerance)
    if not minimum <= distance <= maximum:
        errors.append(
            f"distance {distance:.1f} m outside {minimum:.1f}..{maximum:.1f} m "
            f"(baseline {baseline:.1f} m)"
        )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--endpoint",
        default="http://localhost:8080",
        help="OSRM-compatible base URL (default: %(default)s)",
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    failures = 0
    for case in cases:
        try:
            errors = check_case(args.endpoint, case)
        except (OSError, urllib.error.URLError, ValueError, KeyError) as error:
            errors = [f"request or response error: {error}"]

        if errors:
            failures += 1
            print(f"FAIL {case['id']}: {case['description']}")
            for error in errors:
                print(f"  {error}")
        else:
            print(f"PASS {case['id']}: {case['description']}")

    print(f"\n{len(cases) - failures}/{len(cases)} route regressions passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
