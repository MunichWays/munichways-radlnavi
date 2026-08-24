#!/usr/bin/env python3
"""Regression checks for RadlNavi bicycle profile behavior."""

from __future__ import annotations

import json
import math
import sys
import urllib.error
import urllib.request
from pathlib import Path


ENDPOINT = "http://localhost:18081"
PROFILE = Path(__file__).resolve().parents[1] / "bike.lua"


def route(lat: float) -> dict:
    coordinates = f"11.0000,{lat:.4f};11.0010,{lat:.4f}"
    url = (
        f"{ENDPOINT}/route/v1/bike/{coordinates}"
        "?overview=false&radiuses=8;8"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        return json.load(error)


def assert_routable(lat: float) -> dict:
    response = route(lat)
    assert response["code"] == "Ok", response
    return response["routes"][0]


def assert_blocked(lat: float) -> None:
    response = route(lat)
    assert response["code"] in {"NoRoute", "NoSegment"}, response


def main() -> int:
    profile = PROFILE.read_text(encoding="utf-8")
    assert "max_speed_for_map_matching    = 40/3.6" in profile

    asphalt_duration = assert_routable(48.0000)["duration"]
    for lat in (48.0100, 48.0200, 48.0300):
        duration = assert_routable(lat)["duration"]
        assert math.isclose(duration, asphalt_duration, rel_tol=0.03), (
            lat,
            duration,
            asphalt_duration,
        )

    expected_speed_ratios = {
        48.0400: 2.0,  # wood: 10 km/h instead of 20 km/h
        48.0500: 2.0,  # metal: 10 km/h
        48.0600: 20 / 6,  # grass_paver: 6 km/h
        48.0700: 20 / 3,  # woodchips: 3 km/h
        48.0800: 20 / 9,  # sett: 9 km/h
    }
    for lat, expected_ratio in expected_speed_ratios.items():
        duration = assert_routable(lat)["duration"]
        assert math.isclose(
            duration / asphalt_duration, expected_ratio, rel_tol=0.05
        ), (lat, duration, asphalt_duration, expected_ratio)

    assert_routable(48.1000)
    assert_blocked(48.1100)
    for lat in (48.2000, 48.2100, 48.2200):
        assert_blocked(lat)

    print("profile regressions passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
