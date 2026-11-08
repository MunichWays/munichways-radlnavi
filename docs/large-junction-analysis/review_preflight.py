"""Offline review evidence and conservative graph suggestions; no geometry mutations."""

import gzip
import hashlib
import heapq
import json
from math import cos, radians
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / "backend"))
from src.big_junctions import inside, meters, crossings
from build_review_images import cycling


def fingerprint(site):
    geometry = {"polygon": site["polygon"], "gates": [{k: g[k] for k in
        ("kind", "location", "osmWayId", "label", "forward")} for g in sorted(site["gates"], key=lambda g: g["label"])]}
    return hashlib.sha256(json.dumps(geometry, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def outside_graph(site, reverse=False):
    positions, graph = {}, {}
    for way in site["ways"]:
        if not cycling(way) and way["id"] not in site.get("onRoadWayIds", []):
            continue
        tags = way.get("tags", {})
        if tags.get("bicycle") in {"no", "private", "use_sidepath"} or tags.get("access") in {"no", "private"}:
            continue
        nodes = way["nodes"]
        positions.update({node: [p["lon"], p["lat"]] for node, p in zip(nodes, way["geometry"])})
        direction = tags.get("oneway:bicycle", tags.get("oneway", "no"))
        for a, b in zip(nodes, nodes[1:]):
            edges = [(a, b)] if direction in {"yes", "1"} else ([(b, a)] if direction == "-1" else [(a, b), (b, a)])
            for u, v in edges:
                if reverse:
                    u, v = v, u
                if (not inside(positions[u], site["polygon"]) and not inside(positions[v], site["polygon"])
                    and not crossings([positions[u], positions[v]], site["polygon"])):
                    graph.setdefault(u, []).append((v, meters(positions[u], positions[v])))
    return positions, graph


def reachable(site, gate, positions, graph, limit):
    way = next(w for w in site["ways"] if w["id"] == gate["osmWayId"])
    line = [[p["lon"], p["lat"]] for p in way["geometry"]]
    x, y = gate["location"]
    mx = cos(radians(y))
    def error(pair):
        a, b = pair
        ax, ay = (a[0] - x) * mx, a[1] - y
        dx, dy = (b[0] - a[0]) * mx, b[1] - a[1]
        t = max(0, min(1, -(ax * dx + ay * dy) / (dx * dx + dy * dy))) if dx or dy else 0
        return (ax + t * dx) ** 2 + (ay + t * dy) ** 2
    index = min(range(len(line) - 1), key=lambda i: error(line[i:i + 2]))
    endpoints = way["nodes"][index:index + 2]
    queue = [(meters(gate["location"], positions[n]), n) for n in endpoints
        if not inside(positions[n], site["polygon"])]
    heapq.heapify(queue)
    result = {}
    while queue:
        distance, node = heapq.heappop(queue)
        if distance > limit or node in result:
            continue
        result[node] = distance
        for other, length in graph.get(node, []):
            heapq.heappush(queue, (distance + length, other))
    return result


def merge_suggestions(site, limit=50):
    suggestions = []
    for kind in ("entry", "exit"):
        positions, graph = outside_graph(site, reverse=kind == "entry")
        gates = [g for g in site["gates"] if g["kind"] == kind]
        reach = {g["label"]: reachable(site, g, positions, graph, limit) for g in gates}
        for i, a in enumerate(gates):
            for b in gates[i + 1:]:
                common = reach[a["label"]].keys() & reach[b["label"]].keys()
                if not common:
                    continue
                node = min(common, key=lambda n: (max(reach[a["label"]][n], reach[b["label"]][n]), n))
                suggestions.append({"kind": kind, "gates": [a["label"], b["label"]],
                    "node": node, "location": positions[node],
                    "distancesMeters": [round(reach[g["label"]][node], 1) for g in (a, b)],
                    "action": "Inspect a common gate beyond this node; do not merge automatically."})
    return suggestions


def review(site):
    shared = sorted(g["label"] for g in site["gates"] if g.get("shared"))
    merges = merge_suggestions(site) if site["polygon"] else []
    road = [g["label"] for g in site["gates"] if g["osmWayId"] in site.get("onRoadWayIds", [])]
    return {"id": site["id"], "number": site["number"], "revision": site["version"],
        "status": site["status"], "geometrySha256": fingerprint(site),
        "entries": sum(g["kind"] == "entry" for g in site["gates"]),
        "exits": sum(g["kind"] == "exit" for g in site["gates"]),
        "sharedGates": shared, "carriagewayGates": road, "mergeSuggestions": merges,
        "carriagewaySuggestions": carriageway_suggestions(site) if site["polygon"] else [],
        "unverifiedAccessWays": site.get("review", {}).get("needsAccessVerificationWayIds", []),
        "reviewQuestion": site["note"],
        "caution": "Counts and shared gates do not prove four logical arms or route legality."}


def carriageway_suggestions(site):
    represented = set(site.get("onRoadWayIds", []))
    names = {w.get("tags", {}).get("name") for w in site["ways"] if w["id"] in represented}
    proposals = []
    for way in site["ways"]:
        tags = way.get("tags", {})
        if (way["id"] in represented or tags.get("name") not in names
            or tags.get("highway") not in {"residential", "unclassified", "tertiary", "secondary"}
            or tags.get("bicycle") != "yes" or tags.get("access") in {"no", "private"}):
            continue
        hits = crossings([[p["lon"], p["lat"]] for p in way["geometry"]], site["polygon"])
        if hits:
            proposals.append({"osmWayId": way["id"], "name": tags["name"],
                "crossings": [h["location"] for h in hits],
                "action": "Inspect explicit bicycle=yes carriageway continuation of a represented named arm; no automatic gate approval."})
    return proposals


def validate_references(sites, references):
    by_id = {s["id"]: s for s in sites}
    for reference in references:
        current = by_id[reference["id"]]
        if current["version"] != reference["revision"]:
            # A user-requested new draft must not inherit the old approval.
            # Keep checking the accepted geometry as an archived regression.
            if not (reference.get("archive") and current["status"] == "geometry-draft"
                and not current["polygonApproved"]
                and current.get("review", {}).get("supersedesRevision") == reference["revision"]):
                raise ValueError(f'Unexpected reference revision: {reference["id"]}')
            current = json.loads((ROOT / reference["archive"]).read_text(encoding="utf-8"))
            if current["version"] != reference["revision"] or not current["polygonApproved"]:
                raise ValueError(f'Invalid archived reference: {reference["id"]}')
        if current["status"] != reference["status"] or fingerprint(current) != reference["geometrySha256"]:
            raise ValueError(f'Reference changed: {reference["id"]}; explicit review required.')


def inventory():
    data = json.loads(gzip.decompress((ROOT / "ba09-candidates-osm.json.gz").read_bytes()))["response"]["elements"]
    ways = [w for w in data if w["type"] == "way"]
    groups = []
    for node in (n for n in data if n["type"] == "node"):
        names = sorted({w["tags"]["name"] for w in ways if node["id"] in w.get("nodes", []) and "name" in w.get("tags", {})})
        point = [node["lon"], node["lat"]]
        group = next((g for g in groups if len(names) >= 2 and names == g["roadNames"]
            and all(meters(point, p) <= 80 for p in g["locations"])), None)
        if group is None:
            group = {"roadNames": names, "nodeIds": [], "locations": []}
            groups.append(group)
        group["nodeIds"].append(node["id"])
        group["locations"].append(point)
    return {"candidateNodes": sum(len(g["nodeIds"]) for g in groups), "groups": groups,
        "caution": "Provisional groups of equal road names within 80m, not a count of verified junctions; different-name groups may belong together."}


def main():
    sites = []
    for name in ("review-batch-01-images", "review-batch-02-ba09-images"):
        sites += json.loads((ROOT / name / "review-data.json").read_text(encoding="utf-8"))["sites"]
    references = json.loads((ROOT / "review-reference-cases.json").read_text(encoding="utf-8"))["cases"]
    validate_references(sites, references)
    records = [review(s) for s in sites]
    outcomes = []
    for filename in ("review-batch-01-decisions.json", "review-batch-02-ba09-decisions.json"):
        decisions = json.loads((ROOT / filename).read_text(encoding="utf-8"))["sites"]
        outcomes += [d["efficiency"] for d in decisions.values() if
            d["status"] == "geometry-approved" and isinstance(d.get("efficiency", {}).get("firstPassConfirmed"), bool)]
    output = {"version": 1, "runtimeModified": False, "referenceCasesChecked": len(references),
        "districtInventory": inventory(), "sites": records,
        "efficiency": {"knownFirstPassOutcomes": len(outcomes),
            "firstPassConfirmed": sum(o["firstPassConfirmed"] for o in outcomes),
            "firstPassRate": sum(o["firstPassConfirmed"] for o in outcomes) / len(outcomes) if outcomes else None,
            "note": "Only explicitly recorded outcomes count; unknown history and exclusions do not enter the rate."}}
    (ROOT / "review-preflight.json").write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n', encoding="utf-8")
    rows = ["# Technische Vorprüfung", "", "Offline aus eingefrorenen OSM-Daten. Vorschläge ändern weder Geometrie noch Freigaben.",
        f"{len(references)} bestätigte/ausgeschlossene Referenzfälle unverändert geprüft.", "",
        "Zweirichtungspunkte und mehr als acht Punkte sind zulässig. Vier logische Arme und legale Referenzrouten werden separat nachgewiesen.", "",
        "| Fall | Entry / Exit | Vorschläge zum Zusammenlegen | Eigene Prüffrage |", "| --- | --- | --- | --- |"]
    for record in records:
        if record["status"] not in {"geometry-approved", "permanently-excluded"}:
            hints = "; ".join(f'{" + ".join(m["gates"])} bei OSM-Knoten {m["node"]}' for m in record["mergeSuggestions"]) or "Keine automatische Empfehlung"
            if record["carriagewaySuggestions"]:
                hints += "; Fahrbahn prüfen: " + ", ".join(str(c["osmWayId"]) for c in record["carriagewaySuggestions"])
            if record["unverifiedAccessWays"]:
                hints += "; Radfreigabe prüfen: " + ", ".join(map(str, record["unverifiedAccessWays"]))
            rows.append(f'| K{record["number"]:02d} v{record["revision"]} | {record["entries"]} / {record["exits"]} | {hints} | {record["reviewQuestion"]} |')
    rows += ["", "Vorschläge beruhen auf gerichteter Graph-Erreichbarkeit außerhalb des Polygons, maximal 50 m. Sie sind keine automatische Zusammenlegung oder Freigabe.",
        "", f'Effizienzmessung: {len(outcomes)} ausdrücklich dokumentierte Erstfreigaben; bei fehlender Historie wird keine Erfolgsquote erfunden.', ""]
    (ROOT / "review-preflight.md").write_text('\n'.join(rows), encoding="utf-8")
    print(f'Checked {len(references)} frozen reference cases; prepared {len(records)} site reports.')


if __name__ == "__main__":
    main()
