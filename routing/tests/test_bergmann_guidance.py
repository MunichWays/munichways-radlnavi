#!/usr/bin/env python3
"""Keep both real turns when crossing Landsberger Straße by bicycle."""

from __future__ import annotations

import argparse
import json
import urllib.request


COORDINATES = "11.537721,48.138255;11.538348,48.140515"
EXPECTED = [
    ("depart", None),
    ("turn", "right"),
    ("turn", "left"),
    ("arrive", None),
]


def check(endpoint: str) -> None:
    url = (
        f"{endpoint.rstrip('/')}/route/v1/bike/{COORDINATES}"
        "?alternatives=false&steps=true&overview=false"
    )
    with urllib.request.urlopen(url, timeout=10) as response:
        payload = json.load(response)

    assert payload["code"] == "Ok", payload
    route = payload["routes"][0]
    assert abs(route["distance"] - 270.3) < 0.5, route["distance"]

    steps = route["legs"][0]["steps"]
    actual = [
        (step["maneuver"]["type"], step["maneuver"].get("modifier"))
        for step in steps
    ]
    assert actual == EXPECTED, actual

    right, left = steps[1:3]
    assert abs(right["distance"] - 15.3) < 0.5, right["distance"]
    assert abs(left["distance"] - 89.3) < 0.5, left["distance"]
    for step, expected in (
        (right, (11.538028, 48.13973)),
        (left, (11.538233, 48.139716)),
    ):
        actual_location = step["maneuver"]["location"]
        assert all(
            abs(actual - target) < 0.00002
            for actual, target in zip(actual_location, expected)
        ), actual_location


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True)
    args = parser.parse_args()
    check(args.endpoint)
    print(f"PASS Bergmannstraße/Landsberger Straße: {args.endpoint}")
