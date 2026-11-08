"""Explicit field-test withdrawals take precedence over geometric angle inference."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def apply_exclusions(catalog, report=None):
    decisions = json.loads((ROOT / "review-movement-exclusions.json").read_text(encoding="utf-8"))["decisions"]
    for decision in decisions:
        junction = next(j for j in catalog["junctions"] if j["id"] == decision["junctionId"])
        for movement_id in decision["movementIds"]:
            movement = next(m for m in junction["movements"] if m["id"] == movement_id)
            movement["enabled"] = False
            movement["review"] = {"status": "withdrawn", "date": "2026-11-08", "evidence": decision["reason"]}
            if report is not None:
                evidence = next(j for j in report["junctions"] if j["id"] == decision["junctionId"])
                item = next(m for m in evidence["movements"] if m["id"] == movement_id)
                item["enabled"] = False
                item["reason"] = decision["reason"]
                item["reviewDecision"] = decision["decision"]
    return catalog
