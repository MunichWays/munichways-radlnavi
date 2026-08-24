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


def route_coordinates(coordinates: str) -> dict:
    url = (
        f"{ENDPOINT}/route/v1/bike/{coordinates}"
        "?overview=false&radiuses=8;8"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        return json.load(error)


def route(lat: float) -> dict:
    return route_coordinates(f"11.0000,{lat:.4f};11.0010,{lat:.4f}")


def assert_routable(lat: float) -> dict:
    response = route(lat)
    assert response["code"] == "Ok", response
    return response["routes"][0]


def assert_coordinates_routable(coordinates: str) -> dict:
    response = route_coordinates(coordinates)
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

    road_without_signal = assert_routable(48.3000)
    road_signal = assert_routable(48.3100)
    road_crossing_signal = assert_routable(48.3200)
    path_crossing_signal = assert_routable(48.3300)
    path_road_signal = assert_routable(48.3400)

    assert math.isclose(
        road_signal["weight"] - road_without_signal["weight"], 12, abs_tol=0.3
    ), (road_signal, road_without_signal)
    assert math.isclose(
        road_crossing_signal["weight"], road_without_signal["weight"], abs_tol=0.3
    ), (road_crossing_signal, road_without_signal)
    assert math.isclose(
        path_crossing_signal["weight"] - path_road_signal["weight"],
        12,
        abs_tol=0.3,
    ), (path_crossing_signal, path_road_signal)

    forward_signal = assert_routable(48.3500)
    backward_signal = assert_coordinates_routable(
        "11.0010,48.3500;11.0000,48.3500"
    )
    assert math.isclose(
        forward_signal["weight"] - road_without_signal["weight"],
        12,
        abs_tol=0.3,
    ), (forward_signal, road_without_signal)
    assert math.isclose(
        backward_signal["weight"], road_without_signal["weight"], abs_tol=0.3
    ), (backward_signal, road_without_signal)

    backward_tag_forward_route = assert_routable(48.3800)
    backward_tag_backward_route = assert_coordinates_routable(
        "11.0010,48.3800;11.0000,48.3800"
    )
    assert math.isclose(
        backward_tag_forward_route["weight"],
        road_without_signal["weight"],
        abs_tol=0.3,
    ), (backward_tag_forward_route, road_without_signal)
    assert math.isclose(
        backward_tag_backward_route["weight"] - road_without_signal["weight"],
        12,
        abs_tol=0.3,
    ), (backward_tag_backward_route, road_without_signal)

    right_turn_signal = assert_coordinates_routable(
        "11.0000,48.3600;11.0005,48.3595"
    )
    right_turn_without_signal = assert_coordinates_routable(
        "11.0000,48.3700;11.0005,48.3695"
    )
    assert math.isclose(
        right_turn_signal["weight"], right_turn_without_signal["weight"], abs_tol=0.3
    ), (right_turn_signal, right_turn_without_signal)

    left_turn_signal = assert_coordinates_routable(
        "11.0000,48.3900;11.0005,48.3905"
    )
    left_turn_without_signal = assert_coordinates_routable(
        "11.0000,48.4000;11.0005,48.4005"
    )
    assert math.isclose(
        left_turn_signal["weight"] - left_turn_without_signal["weight"],
        12,
        abs_tol=0.3,
    ), (left_turn_signal, left_turn_without_signal)

    level_crossing = assert_routable(48.4100)
    assert math.isclose(
        level_crossing["weight"] - road_without_signal["weight"],
        12,
        abs_tol=0.3,
    ), (level_crossing, road_without_signal)

    print("profile regressions passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
