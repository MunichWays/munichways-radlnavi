"""Compare the proposed eligibility guard on saved fixtures, not a Dart replay.

Run from any directory: python docs/osrm-standard-analysis/compare_offset_policy.py
Local metre projection; only these non-looping fixtures are supported.
"""

import json
from pathlib import Path

from inspect_geometry import inspect


def compare(path):
    diagnosis = inspect(path)
    route = json.loads(path.read_text(encoding="utf-8"))["response"]["routes"][0]
    raw = [step["maneuver"] for leg in route["legs"] for step in leg["steps"]
           if step["maneuver"]["type"] not in ("depart", "arrive", "notification")]
    adjusted = []
    for maneuver, measured in zip(raw, diagnosis["maneuvers"]):
        modifier = maneuver.get("modifier")
        # These fixtures have sufficient geometry before/after each maneuver.
        if maneuver["type"] == "turn" and modifier in ("left", "right"):
            if 15 <= abs(measured["angle_12m_deg"]) <= 50:
                modifier = "slight " + modifier
        adjusted.append({"type": maneuver["type"], "modifier": modifier})
    pair = diagnosis["opposite_pairs"][0] if len(adjusted) == 2 and diagnosis["opposite_pairs"] else None
    eligible = len(adjusted) == 2 and all(m["type"] == "turn" for m in adjusted) and (
        [m["modifier"] for m in adjusted] in
        (["slight left", "slight right"], ["slight right", "slight left"]))
    old_removes = bool(pair and pair["matches_app_offset_thresholds"])
    return {
        "case": path.stem,
        "scope": "Approximate fixture diagnosis, not execution of VoiceGuidance",
        "measured_maneuvers": diagnosis["maneuvers"],
        "after_existing_adjustment": adjusted,
        "pair": pair,
        "old_rule_removes_pair": old_removes,
        "proposed_rule_removes_pair": old_removes and eligible,
        "geometry_addition_candidates": sum(c["passes_geometry_addition_thresholds"] for c in diagnosis["corners"]),
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    print(json.dumps([compare(root / f"{name}.json") for name in
                      ("birketweg", "balanstrasse-app-test", "lenbachplatz")], indent=2))
