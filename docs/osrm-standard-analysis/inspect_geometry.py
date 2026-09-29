"""Offline geometry diagnostics for saved API responses; not a Flutter replay.

Run: python docs/osrm-standard-analysis/inspect_geometry.py
Uses a local metre projection. Values approximate the app's geodesic distances.
"""

import json
import math
from pathlib import Path


def inspect(path):
    route = json.loads(path.read_text(encoding="utf-8"))["response"]["routes"][0]
    coordinates = route["geometry"]["coordinates"]
    origin = coordinates[0]
    scale = 111320 * math.cos(math.radians(origin[1]))

    def xy(point):
        return ((point[0] - origin[0]) * scale, (point[1] - origin[1]) * 111320)

    points = list(map(xy, coordinates))
    distances = [0.0]
    for first, second in zip(points, points[1:]):
        distances.append(distances[-1] + math.dist(first, second))

    def position(coordinate):
        # All saved maneuver locations are exact overview vertices.
        return distances[coordinates.index(coordinate)]

    def sample(distance):
        distance = max(0, min(distances[-1], distance))
        for i in range(1, len(points)):
            if distances[i] >= distance:
                fraction = (distance - distances[i - 1]) / (distances[i] - distances[i - 1])
                return tuple(a + fraction * (b - a) for a, b in zip(points[i - 1], points[i]))
        return points[-1]

    def angle(a, b, c, d):
        ux, uy = b[0] - a[0], b[1] - a[1]
        vx, vy = d[0] - c[0], d[1] - c[1]
        return math.degrees(math.atan2(ux * vy - uy * vx, ux * vx + uy * vy))

    maneuvers = [s["maneuver"] for leg in route["legs"] for s in leg["steps"]]
    relevant = [m for m in maneuvers if m["type"] not in ("depart", "arrive", "notification")]
    result = {"case": path.stem, "maneuvers": [], "opposite_pairs": [], "corners": []}
    for maneuver in relevant:
        distance = position(maneuver["location"])
        result["maneuvers"].append({
            "type": maneuver["type"], "modifier": maneuver.get("modifier"),
            "route_m": round(distance, 2),
            "angle_12m_deg": round(angle(sample(distance - 12), sample(distance), sample(distance), sample(distance + 12)), 2),
        })
    for first, second in zip(relevant, relevant[1:]):
        a, b = first.get("modifier", ""), second.get("modifier", "")
        if not (("left" in a and "right" in b) or ("right" in a and "left" in b)):
            continue
        d1, d2 = position(first["location"]), position(second["location"])
        heading = abs(angle(sample(d1 - 12), sample(d1), sample(d2), sample(d2 + 12)))
        result["opposite_pairs"].append({
            "gap_m": round(d2 - d1, 2), "heading_change_deg": round(heading, 2),
            "matches_app_offset_thresholds": 0 < d2 - d1 <= 30 and heading <= 25,
        })
    for i in range(1, len(points) - 1):
        turn = angle(points[i - 1], points[i], points[i], points[i + 1])
        if abs(turn) < 25:
            continue
        incoming = distances[i] - distances[i - 1]
        outgoing = distances[i + 1] - distances[i]
        protected_gap = min(abs(position(m["location"]) - distances[i]) for m in maneuvers)
        result["corners"].append({
            "location_lon_lat": coordinates[i], "route_m": round(distances[i], 2),
            "signed_angle_deg_left_positive": round(turn, 2),
            "incoming_m": round(incoming, 2), "outgoing_m": round(outgoing, 2),
            "nearest_raw_maneuver_m": round(protected_gap, 2),
            "passes_geometry_addition_thresholds": incoming >= 7 and outgoing >= 7
            and 60 <= abs(turn) <= 135 and protected_gap >= 25,
        })
    return result


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    for name in ("birketweg", "schrammerstrasse", "waisenhausstrasse", "lenbachplatz"):
        print(json.dumps(inspect(root / f"{name}.json"), ensure_ascii=False, indent=2))
