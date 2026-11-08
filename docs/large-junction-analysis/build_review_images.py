"""Offline, reproducible review sheets. Draft geometry is NEVER a runtime input.

Uses OSM cycling branch/crossing nodes to suggest a buffered convex envelope.
Non-standard gate counts are deliberately withheld from the simple approval flow.
No route legality or connectivity approval is inferred from this drawing.
"""

import gzip
import hashlib
import html
import json
from collections import Counter, defaultdict
from math import atan2, cos, degrees, hypot, radians
from pathlib import Path

from build_balan_pilot import visits

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "review-batch-01-images"
MAJOR = {"primary", "secondary", "tertiary", "primary_link", "secondary_link", "tertiary_link", "residential", "unclassified"}


def cycling(w):
    t = w.get("tags", {})
    return (t.get("highway") in {"cycleway", "path", "footway"}
            and (t.get("highway") == "cycleway" or t.get("bicycle") in {"yes", "designated"})
            and t.get("bicycle") not in {"no", "private"}
            and t.get("access") not in {"no", "private"}
            and t.get("area") != "yes")


def hull(points):
    points = sorted(set(points))
    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
    lower, upper = [], []
    for source, dest in [(points, lower), (points[::-1], upper)]:
        for p in source:
            while len(dest) >= 2 and cross(dest[-2], dest[-1], p) <= 0:
                dest.pop()
            dest.append(p)
    return lower[:-1] + upper[:-1]


def number_gates(gates, center, project):
    def angle(g):
        x, y = project(g["location"])
        return degrees(atan2(x-center[0], y-center[1])) % 360
    gates.sort(key=angle)
    # Start at the first exit clockwise from north, then preserve physical order.
    start = next((i for i, g in enumerate(gates) if g["kind"] == "exit"), 0)
    gates[:] = gates[start:] + gates[:start]
    counts = Counter()
    for g in gates:
        counts[g["kind"]] += 1
        g["label"] = f'{g["kind"].title()}-{counts[g["kind"]]}'
    return gates


def extract_gates(ways, polygon, project, road_way_ids=(), excluded=()):
    gates=[]
    for w in ways:
        if w["id"] in excluded or not (cycling(w) or w["id"] in road_way_ids):
            continue
        points=[[v["lon"],v["lat"]] for v in w["geometry"]]
        direction=w["tags"].get("oneway:bicycle",w["tags"].get("oneway","no"))
        if direction=="-1": points.reverse()
        for hit in visits(points,polygon,project):
            a,b=(project(points[hit["segmentIndex"]+j]) for j in (0,1))
            length=hypot(b[0]-a[0],b[1]-a[1])
            if length<.001: continue
            gate={"kind":hit["kind"],"location":hit["location"],"osmWayId":w["id"],
                  "directionBasis":direction,"forward":[(b[0]-a[0])/length,(b[1]-a[1])/length]}
            options=[gate]
            if direction not in {"yes","1","-1"}:
                gate["shared"]=True
                options.append(dict(gate,kind="exit" if gate["kind"]=="entry" else "entry",
                                    forward=[-v for v in gate["forward"]]))
            for g in options:
                if not any(g["kind"]==prev["kind"] and hypot(*(a-b for a,b in zip(project(g["location"]),project(prev["location"]))))<1 for prev in gates):
                    gates.append(g)
    return gates


def check_review_fingerprint(site, review):
    if review["status"]=="geometry-approved":
        geometry={"polygon":site["polygon"],"gates":[{k:g[k] for k in ("kind","location","osmWayId","label","forward")} for g in sorted(site["gates"],key=lambda g:g["label"])]}
        fingerprint=hashlib.sha256(json.dumps(geometry,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        if fingerprint!=review["reviewedGeometrySha256"]:
            raise ValueError(f'Reviewed geometry changed for {site["id"]}; existing approval cannot be inherited.')


def apply_review(site, review):
    site["review"]=review
    site["status"]=review["status"]
    site["polygonApproved"]=review["status"]=="geometry-approved"
    site["note"]=review["note"]
    site["version"]=review.get("revision",1)
    if "polygon" not in review:
        check_review_fingerprint(site,review)
        return
    site["polygon"]=review["polygon"]
    site["basis"]=review.get("geometryBasis", "Manual revision following Thomas's annotated v1 review; gate coordinates intersect frozen OSM geometry.")
    lon,lat=site["origin"]
    mx=111320*cos(radians(lat))
    project=lambda a:((a[0]-lon)*mx,(a[1]-lat)*111320)
    site["onRoadWayIds"]=review.get("onRoadWayIds",[])
    preferred=review.get("preferredGateWayIds",[])
    gate_ways=sorted(site["ways"],key=lambda w:w["id"] not in preferred)
    site["gates"]=extract_gates(gate_ways,site["polygon"],project,
                                site["onRoadWayIds"],review.get("excludedGateWayIds",[]))
    filtered=[]
    for g in site["gates"]:
        excluded=review.get("excludedGateDirections",{}).get(str(g["osmWayId"]),[])
        if g["kind"] in excluded:
            continue
        if excluded:
            g["shared"]=False
            g["scopeNote"]="Only the included approach is represented; the opposite movement towards the excluded arm remains outside guidance scope. OSM two-way legality is unchanged."
        filtered.append(g)
    site["gates"]=filtered
    for g in site["gates"]:
        key=f'{g["osmWayId"]}:{g["kind"]}'
        g["label"]=review["gateLabels"][key]
    site["gates"].sort(key=lambda g:(int(g["label"].split("-")[1]),0 if g["kind"]=="exit" else 1))
    check_review_fingerprint(site,review)


def status_text(site):
    return {"geometry-draft":"Korrigierter Entwurf – Sichtprüfung offen",
            "geometry-approved":"Geometrie bestätigt – Freigabestand siehe Prüfbericht",
            "permanently-excluded":"Dauerhaft ausgeschlossen – Fall geschlossen",
            "withheld-needs-technical-review":"Zurückgestellt – technische Klärung offen"}[site["status"]]


def review_summary(sites):
    parts=[]
    for status,label in [("geometry-approved","Geometrisch bestätigt"),
                         ("geometry-draft","Zur Sichtprüfung"),
                         ("withheld-needs-technical-review","Zurückgestellt"),
                         ("permanently-excluded","Dauerhaft ausgeschlossen")]:
        names=[f'K{s["number"]:02d} v{s["version"]}' for s in sites if s["status"]==status]
        if names: parts.append(label+": "+", ".join(names)+".")
    return " ".join(parts)


def prepare_site(feature, all_ways):
    p = feature["properties"]
    lon, lat = feature["geometry"]["coordinates"]
    mx = 111320*cos(radians(lat))
    project = lambda a: ((a[0]-lon)*mx, (a[1]-lat)*111320)
    inverse = lambda a: [lon+a[0]/mx, lat+a[1]/111320]
    ways = []
    for w in all_ways:
        points = [[v["lon"], v["lat"]] for v in w.get("geometry", [])]
        if len(points) > 1 and min(hypot(*project(a)) for a in points) < 185:
            ways.append(w)
    bike = [w for w in ways if cycling(w)]
    adjacent, positions, road_nodes = defaultdict(set), {}, set()
    for w in ways:
        if w.get("tags", {}).get("highway") in MAJOR:
            road_nodes.update(w.get("nodes", []))
    for w in bike:
        for node, v in zip(w["nodes"], w["geometry"]):
            positions[node] = project([v["lon"], v["lat"]])
        for a, b in zip(w["nodes"], w["nodes"][1:]):
            adjacent[a].add(b)
            adjacent[b].add(a)
    seeds = [xy for node, xy in positions.items()
             if hypot(*xy) < 55 and (len(adjacent[node]) >= 3 or node in road_nodes)]
    base = hull(seeds)
    polygon, gates = [], []
    if len(base) >= 3:
        # Eight-metre padding includes kerbs/islands around the detected crossing nodes.
        expanded = hull([(x+dx, y+dy) for x, y in base
                         for dx, dy in [(-8,-8), (-8,8), (8,-8), (8,8)]])
        polygon = [inverse(a) for a in expanded + expanded[:1]]
        gates = extract_gates(ways, polygon, project)
    center = (sum(x for x,y in base)/len(base), sum(y for x,y in base)/len(base)) if base else (0,0)
    number_gates(gates, center, project)
    simple = (len(gates) == 8 and Counter(g["kind"] for g in gates) == {"entry": 4, "exit": 4}
              and not any(g.get("shared") for g in gates)
              and all(g["kind"] != gates[(i+1) % len(gates)]["kind"] for i,g in enumerate(gates)))
    # A drawing cannot establish route connectivity; every site stays disabled.
    return {"id": p["id"], "name": p["name"], "number": p["reviewOrder"],
            "version": 1, "enabled": False, "polygonApproved": False,
            "status": "geometry-draft" if simple else "withheld-needs-technical-review",
            "note": p["nextCheck"], "polygon": polygon, "gates": gates,
            "seedCount": len(seeds), "ways": ways, "origin": [lon,lat],
            "basis": "Unreviewed convex envelope of cycling branch/crossing nodes within 55m, padded 8m; no movement approval."}


def draw(site):
    lon, lat = site["origin"]
    mx = 111320*cos(radians(lat))
    xy = lambda a: ((a[0]-lon)*mx, (a[1]-lat)*111320)
    poly = [xy(a) for a in site["polygon"]]
    extent = max([70] + [max(abs(x), abs(y))+28 for x,y in poly])
    scale = min(5.1, 370/extent)
    point = lambda a: [round(600+xy(a)[0]*scale,2), round(510-xy(a)[1]*scale,2)]
    commands = []
    def text(value, x, y, size=15, color="#263238"):
        commands.append({"kind":"text", "text":value, "x":x, "y":y, "size":size, "color":color})
    def line(points, color, width=2, fill=None):
        commands.append({"kind":"polygon" if fill else "line", "points":points, "color":color, "width":width, "fill":fill})
    text(f'K{site["number"]:02d} · {site["name"]}', 28, 24, 21)
    status = status_text(site)
    text(f'v{site["version"]} · {status} · NICHT AKTIV',28,58,16,"#8b256a")
    # Clip map content to the central panel so long OSM ways cannot cover the header.
    commands.append({"kind":"clip", "x":180,"y":100,"width":840,"height":800})
    if site["polygon"]:
        line([point(a) for a in site["polygon"]],"#8c269a",2.5,"#efe3f2")
    for w in sorted(site["ways"], key=lambda w: cycling(w) or w["id"] in site.get("onRoadWayIds",[])):
        t = w.get("tags", {})
        is_bike = cycling(w) or w["id"] in site.get("onRoadWayIds",[])
        color = "#4e6c66" if is_bike else "#d3d5d7"
        width = 3 if is_bike else (12 if t.get("highway") in MAJOR else 1.4)
        coordinates=[point([v["lon"],v["lat"]]) for v in w.get("geometry",[])]
        if w["id"] in site.get("onRoadWayIds",[]):
            line(coordinates,"#d3d5d7",12)
        line(coordinates,color,width)
    if site["polygon"]:
        line([point(a) for a in site["polygon"]],"#8c269a",2.5)
    commands.append({"kind":"unclip"})
    # Road names sit away from the central crossings. One name per road.
    names, name_boxes = set(), []
    for w in site["ways"]:
        t = w.get("tags", {})
        name = t.get("name")
        if not name or name in names or t.get("highway") not in MAJOR:
            continue
        options = [(hypot(*xy([v["lon"],v["lat"]])),v) for v in w.get("geometry",[])]
        options = [(d,v) for d,v in options if extent*.72 < d < extent*1.05]
        if not options and w["id"] in site.get("onRoadWayIds",[]):
            options=[(hypot(*xy([v["lon"],v["lat"]])),v) for v in w.get("geometry",[]) if hypot(*xy([v["lon"],v["lat"]])) < extent*.9]
        if options:
            _, v = min(options, key=lambda pair:abs(pair[0]-extent*.87))
            px,py=point([v["lon"],v["lat"]])
            tx,ty=max(190,min(px,930-len(name)*7)),max(110,min(py,860))
            width=len(name)*7
            while any(tx < bx+bw and tx+width > bx and abs(ty-by)<18 for bx,by,bw in name_boxes):
                ty+=18
            text(name,tx,ty,13,"#62676b")
            name_boxes.append((tx,ty,width))
            names.add(name)
    # Leader labels in separate side columns; deterministic spacing avoids collisions.
    sides = defaultdict(list)
    for g in site["gates"]:
        x,y=point(g["location"])
        sides["right" if x>=600 else "left"].append((y,x,g))
    for side, entries in sides.items():
        entries.sort(key=lambda e:(e[0],e[1],e[2]["kind"]))
        labels=[]
        for y,x,g in entries:
            target=max(145,min(y,850))
            labels.append(max(target, labels[-1]+31 if labels else 145))
        if labels and labels[-1]>860:
            shift=labels[-1]-860
            labels=[y-shift for y in labels]
        for (y,x,g),label_y in zip(entries,labels):
            color="#087c58" if g["kind"]=="entry" else "#1262b5"
            label_x=1030 if side=="right" else 24
            edge=1023 if side=="right" else 173
            line([[x,y],[edge,label_y+9]],color,1)
            commands.append({"kind":"circle","x":x,"y":y,"radius":6,"color":color,"fill":"#ffffff"})
            text(g["label"]+(" *" if g.get("shared") else ""),label_x,label_y,17,color)
            dx,dy=g["forward"][0],-g["forward"][1]
            # The arrow follows OSM way order, including oneway:bicycle overrides.
            ax,ay=x+dx*20,y+dy*20
            line([[x+dx*8,y+dy*8],[ax,ay]],color,2)
            line([[ax-dx*7-dy*4,ay-dy*7+dx*4],[ax,ay],[ax-dx*7+dy*4,ay-dy*7-dx*4]],color,2)
    signal=site.get("review",{}).get("signalNode")
    if signal:
        x,y=point(signal["location"])
        commands.append({"kind":"circle","x":x,"y":y,"radius":3,"color":"#202020","fill":"#202020"})
        text("Ampel",x+12,y-27,13,"#202020")
    text("N ↑",1100,105,19)
    bar=20*scale
    line([[200,890],[200+bar,890]],"#263238",3)
    text("20 m",200,895,12)
    text("Violett: Kreuzungsfläche  |  Grün: Entry  |  Blau: Exit  |  Graugrün: Radwege / geprüfte Straßenführung",28,938,14)
    text("Nummern im Uhrzeigersinn; Entry/Exit gleicher Nummer sind kein Fahrbeziehungspaar.",28,963,13)
    text("* gemeinsamer Punkt für beide Richtungen · OSM © OpenStreetMap-Mitwirkende, ODbL",28,986,12)
    # Break long notes into complete, readable lines.
    import textwrap
    for i,value in enumerate(textwrap.wrap(site["note"],width=138)):
        text(value,28,1017+i*22,14)
    return commands


def svg(commands):
    out=['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1100" viewBox="0 0 1200 1100"><rect width="1200" height="1100" fill="white"/><defs><clipPath id="map"><rect x="180" y="100" width="840" height="800"/></clipPath></defs>']
    for c in commands:
        kind=c["kind"]
        if kind=="clip": out.append('<g clip-path="url(#map)">')
        elif kind=="unclip": out.append('</g>')
        elif kind=="text": out.append(f'<text x="{c["x"]}" y="{c["y"]+c["size"]}" font-family="Arial,sans-serif" font-size="{c["size"]}" fill="{c["color"]}">{html.escape(c["text"])}</text>')
        elif kind=="circle": out.append(f'<circle cx="{c["x"]}" cy="{c["y"]}" r="{c["radius"]}" fill="{c["fill"]}" stroke="{c["color"]}" stroke-width="2"/>')
        else:
            tag="polygon" if kind=="polygon" else "polyline"
            points=" ".join(f'{x},{y}' for x,y in c["points"])
            out.append(f'<{tag} points="{points}" fill="{c.get("fill") or "none"}" stroke="{c["color"]}" stroke-width="{c["width"]}" stroke-linejoin="round"/>')
    return "".join(out)+'</svg>'


def main():
    OUT.mkdir(exist_ok=True)
    snapshot=json.loads(gzip.decompress((ROOT/"review-batch-01-osm.json.gz").read_bytes()))
    batch=json.loads((ROOT/"review-batch-01.geojson").read_text(encoding="utf-8"))
    sites=[prepare_site(f,snapshot["response"]["elements"]) for f in batch["features"]]
    baseline=ROOT/"review-batch-01-v1-geometry.json"
    if not baseline.exists():
        baseline.write_text(json.dumps({"revision":1,"osmRetrievedAt":snapshot["retrievedAt"],
            "sites":[{k:s[k] for k in ("id","number","polygon","gates")} for s in sites]},
            ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    decisions=json.loads((ROOT/"review-batch-01-decisions.json").read_text(encoding="utf-8"))["sites"]
    for site in sites:
        if site["id"] in decisions:
            apply_review(site,decisions[site["id"]])
    previous_path=OUT/"review-data.json"
    if previous_path.exists():
        previous={s["id"]:s for s in json.loads(previous_path.read_text(encoding="utf-8"))["sites"]}
        for site in sites:
            old=previous.get(site["id"])
            if not old:
                continue
            if site["version"]>old["version"]:
                continue  # Explicit revision and label migration recorded in the decisions file.
            if len(old["gates"])!=len(site["gates"]):
                raise ValueError(f'Gate layout changed for {site["id"]}; explicitly review a new revision before rebuilding.')
            used=set()
            for gate in site["gates"]:
                options=[g for g in old["gates"] if g["osmWayId"]==gate["osmWayId"] and g["kind"]==gate["kind"] and g["label"] not in used]
                if not options:
                    raise ValueError(f'Gate identity changed for {site["id"]}; preserve labels manually in a new revision.')
                match=min(options,key=lambda g:hypot(g["location"][0]-gate["location"][0],g["location"][1]-gate["location"][1]))
                gate["label"]=match["label"]
                used.add(gate["label"])
            site["version"]=old["version"]
    for site in sites:
        name=f'K{site["number"]:02d}-{site["id"]}'
        commands=draw(site)
        (OUT/f'{name}.svg').write_text(svg(commands),encoding="utf-8")
        (OUT/f'{name}.drawing.json').write_text(json.dumps(commands,ensure_ascii=False),encoding="utf-8")
        print(name,site["status"],len(site["gates"]),"gates")
    evidence={"version":1,"enabled":False,"osmRetrievedAt":snapshot["retrievedAt"],"sites":sites}
    (OUT/"review-data.json").write_text(json.dumps(evidence,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    cards=[]
    summary=review_summary(sites)
    rows=["# Bildprüfung – Runde 1", "", "[Bildergalerie](index.html) · [Gesamtübersicht](overview.png)", "",
          "Norden oben. Diese Galerie dokumentiert die Geometrieprüfung; der aktuelle Freigabestand steht im [Prüfbericht](../review-batch-01-release.md).", "", summary, "",
          "Prüfen: richtige Radwegseite und Pfeilrichtung; alle Querungen, Inseln und Warteplätze innerhalb; keine Nachbarkreuzung eingeschlossen.", "",
          "Rückmeldung beispielsweise: `K05 v2 passt` oder `K06 Entry-2 weiter nach außen`.",
          "Nummern laufen im Uhrzeigersinn ab dem ersten Exit nach Norden. Entry und Exit",
          "gleicher Nummer bezeichnen kein Fahrbeziehungspaar. Ein Stern markiert einen",
          "gemeinsam genutzten Punkt bei Zweirichtungsführung. IDs bleiben beim erneuten",
          "Rendern erhalten; eine geänderte Punktstruktur erfordert eine explizite neue Revision.", "",
          "K05 v2: Entry-4 und Entry-5 zu Entry-4 am gemeinsamen Knoten zusammengelegt; Polygon erweitert, Exit-1 leicht verschoben.",
          "K06 v2: Lachnerstraße auf der Fahrbahn mit Entry-2 / Exit-3 ergänzt; folgende Nummern neu vergeben, Polygon unverändert. Rufinistraße bleibt ausgeschlossen.", "",
          "| ID | Bild | Status | Deine Rückmeldung |", "| --- | --- | --- | --- |"]
    for site in sites:
        name=f'K{site["number"]:02d}-{site["id"]}'
        status=f'v{site["version"]} · {status_text(site)}'
        cards.append(f'<article><h2>K{site["number"]:02d} · {html.escape(site["name"])}</h2><p>{status}</p><a href="{name}.png"><img src="{name}.svg" alt="Prüfbild {html.escape(site["name"])}"/></a><p><a href="{name}.png">PNG öffnen</a> · <a href="{name}.svg">SVG vergrößern</a></p></article>')
        rows.append(f'| K{site["number"]:02d} | [{site["name"]}]({name}.png) | {status} | |')
    page='<!doctype html><html lang="de"><meta charset="utf-8"><title>Kreuzungen – Bildprüfung Runde 1</title><style>body{font:17px Arial;margin:24px;background:#f3f4f5;color:#263238}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(460px,1fr));gap:20px}article{background:white;padding:16px;border:1px solid #ddd}h2{font-size:19px}img{width:100%;height:auto}p{max-width:1000px;line-height:1.5}</style><h1>Bildprüfung Runde 1 · aktualisiert</h1><p>'+html.escape(summary)+'</p><p>Der aktuelle Aktivierungsstand und verbleibende Ausnahmen stehen im <a href="../review-batch-01-release.md">Freigabebericht</a>.</p><p>K05 v2: gemeinsamer Entry-4 am östlichen Verzweigungspunkt; Fläche erweitert, Exit-1 leicht verschoben. K06 v2: Lachnerstraße mit Entry-2 / Exit-3 auf der Fahrbahn; Fläche unverändert, folgende Nummern angepasst.</p><p>In K08 v2 liegen Entry-2 und Exit-3 gemeinsam an der Fahrbahnampel der Hackerbrücke. In K10 v2 liegt der normale Entry-2 weiter nördlich; Wilramstraße ist ausgeschlossen.</p><p>Rückmeldung zum Beispiel: „K05 v2 passt“. Nummern folgen dem Uhrzeigersinn und bezeichnen keine Fahrbeziehungspaare. Ein Klick öffnet das PNG in voller Größe.</p><main>'+''.join(cards)+'</main></html>'
    (OUT/"index.html").write_text(page,encoding="utf-8")
    (OUT/"README.md").write_text("\n".join(rows)+"\n",encoding="utf-8")
    from organize_review_images import main as organize_images
    organize_images()
    if (ROOT / "review-reference-cases.json").exists():
        from review_preflight import main as preflight
        preflight()


if __name__=="__main__":
    main()
