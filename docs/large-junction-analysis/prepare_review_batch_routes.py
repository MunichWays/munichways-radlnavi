"""Verify explicitly reviewed batch-01 movements with real, cached API routes.

No permissive runtime changes. A failed route remains individually disabled.
Run with --collect to obtain missing evidence, then offline to reproduce checks.
"""

import argparse
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import json
from math import atan2, ceil, cos, degrees, hypot, radians
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
BACKEND=ROOT.parents[1]/"backend"
sys.path.insert(0,str(BACKEND))
from src.big_junctions import (add_guidance, catalog, crossings, inside, meters,
                               point_at, validate_catalog)

FIXTURES=BACKEND/"tests/fixtures/big-junctions/batch-01"
MANIFEST=ROOT/"review-batch-01-route-requests.json"
LEFT={"west":"north","north":"east","east":"south","south":"west"}
STRAIGHT={"west":"east","north":"south","east":"west","south":"north"}
RIGHT={v:k for k,v in LEFT.items()}
ARMS={"north":("Entry-4","Exit-1"),"east":("Entry-1","Exit-2"),
      "south":("Entry-2","Exit-3"),"west":("Entry-3","Exit-4")}


def allowed(w, road_ids):
    t=w.get("tags",{})
    if t.get("access") in {"no","private"} or t.get("bicycle") in {"no","private","use_sidepath","dismount"} or t.get("motorroad")=="yes":return False
    if t.get("highway")=="cycleway":return True
    if t.get("highway") in {"path","footway"}:return t.get("bicycle") in {"yes","designated"}
    return (t.get("highway") in {"primary","secondary","tertiary","residential","unclassified","primary_link","secondary_link","tertiary_link"}
            and (w["id"] in road_ids or t.get("bicycle") in {"yes","designated"}))


def graph(ways, road_ids):
    edges=[]
    for w in ways:
        if not allowed(w,road_ids):continue
        direction=w["tags"].get("oneway:bicycle",w["tags"].get("oneway","no"))
        points=[[v["lon"],v["lat"]] for v in w["geometry"]]
        for a,b in zip(points,points[1:]):
            if meters(a,b)<.01:continue
            if direction in {"-1"}:edges.append((b,a,w["id"]))
            elif direction in {"yes","1"}:edges.append((a,b,w["id"]))
            else:edges.extend([(a,b,w["id"]),(b,a,w["id"])])
    return edges


def unit(a,b):
    x=(b[0]-a[0])*cos(radians(a[1]));y=b[1]-a[1];n=hypot(x,y)
    return (x/n,y/n) if n else (0,0)


def endpoint(gate,edges,kind,ring,distance=45):
    """Walk 45m outward on the legal directed network; never extrapolate."""
    p=gate["location"];mx=111320*cos(radians(p[1]));candidates=[]
    for a,b,w in edges:
        if w!=gate["osmWayId"]:continue
        d=unit(a,b)
        if sum(x*y for x,y in zip(d,gate["forward"]))<.95:continue
        x,y=(b[0]-a[0])*mx,(b[1]-a[1])*111320
        t=max(0,min(1,((p[0]-a[0])*mx*x+(p[1]-a[1])*111320*y)/(x*x+y*y)))
        q=[a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])]
        candidates.append((meters(p,q),a,b,w))
    if not candidates:raise ValueError("No legal directed gate segment")
    gap,a,b,w=min(candidates,key=lambda c:c[0])
    if gap>.2:raise ValueError("Gate not on directed source way")
    line=[p];next_point=a if kind=="entry" else b
    outward=[-v for v in gate["forward"]] if kind=="entry" else gate["forward"]
    if meters(p,next_point)>.01:line.append(next_point)
    else:next_point=p
    used=set()
    while sum(meters(a,b) for a,b in zip(line,line[1:]))<distance:
        options=[]
        for a,b,w in edges:
            origin,target=(b,a) if kind=="entry" else (a,b)
            if meters(origin,next_point)>.01:continue
            key=(tuple(origin),tuple(target))
            if key in used or any(meters(target,x)<.01 for x in line):continue
            d=unit(origin,target);dot=sum(x*y for x,y in zip(outward,d))
            if dot>=.5:options.append((dot,target,w,key,d))
        options.sort(key=lambda x:x[0],reverse=True)
        if not options:raise ValueError("No unambiguous 45m legal gate continuation")
        if len(options)>1 and options[0][0]-options[1][0]<.03 and meters(options[0][1],options[1][1])>.2:
            raise ValueError("Ambiguous gate continuation")
        _,next_point,w,key,outward=options[0];used.add(key);line.append(next_point)
    sample=point_at(line,distance)
    if inside(sample,ring):raise ValueError("Reference endpoint remains inside polygon")
    return sample


def corridor_check(line,edges):
    origin=line[0];mx=111320*cos(radians(origin[1]));xy=lambda p:((p[0]-origin[0])*mx,(p[1]-origin[1])*111320)
    segments=[(xy(a),xy(b),w) for a,b,w in edges];used=set()
    for start,end in zip(line,line[1:]):
        a,b=xy(start),xy(end);dx,dy=b[0]-a[0],b[1]-a[1];length=hypot(dx,dy)
        if length<.25:continue
        count=max(1,ceil(length/2))
        for i in range(count):
            x,y=a[0]+dx*(i+.5)/count,a[1]+dy*(i+.5)/count;best=(float("inf"),None)
            for c,d,w in segments:
                rx,ry=d[0]-c[0],d[1]-c[1];norm=hypot(rx,ry)
                if not norm or (dx*rx+dy*ry)/(length*norm)<.85:continue
                t=max(0,min(1,((x-c[0])*rx+(y-c[1])*ry)/(norm*norm)))
                gap=hypot(x-c[0]-t*rx,y-c[1]-t*ry)
                if gap<best[0]:best=(gap,w)
            if best[0]>1.25:raise ValueError("Inner route lacks legal directed OSM support within 1.25m")
            used.add(best[1])
    return sorted(used)


def fetch(url,path,manifest,collect):
    key=path.name
    if path.exists() and manifest.get(key,{}).get("url")==url:
        return json.loads(path.read_text(encoding="utf-8"))
    if not collect:raise ValueError("Missing cached route; run --collect")
    for attempt in range(2):
        try:
            with urlopen(Request(url,headers={"User-Agent":"MunichWays-Junction-Catalog/1.0"}),timeout=30) as response:value=json.load(response)
            break
        except (HTTPError,TimeoutError) as error:
            if attempt or isinstance(error,HTTPError) and error.code not in {429,502,503,504}:raise
    path.write_text(json.dumps(value,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    manifest[key]={"url":url,"retrievedAt":datetime.now(timezone.utc).isoformat()}
    MANIFEST.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return value


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--collect",action="store_true");args=parser.parse_args()
    data=json.loads((ROOT/"review-batch-01-images/review-data.json").read_text(encoding="utf-8"))
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    FIXTURES.mkdir(parents=True,exist_ok=True)
    proposed=deepcopy(catalog());proposed["version"]="munich-big-junctions-v3"
    ids={s["id"] for s in data["sites"]};proposed["junctions"]=[j for j in proposed["junctions"] if j["id"] not in ids]
    decisions=json.loads((ROOT/"junction-review-decisions.json").read_text(encoding="utf-8"))["decisions"]
    proposed["excluded"]=[dict({k:v for k,v in d.items() if k!="junctionId"},id=d["junctionId"]) for d in decisions]
    report={"catalogVersion":proposed["version"],"junctions":[],"rightTurnChecks":[]}
    for site in data["sites"]:
        if site["number"] in {7,9}:continue
        if not site["polygonApproved"]:raise ValueError(f'Geometry not approved: {site["id"]}')
        ring=site["polygon"];gates={g["label"]:g for g in site["gates"]};edges=graph(site["ways"],site.get("onRoadWayIds",[]))
        junction={"id":site["id"],"name":site["name"],"enabled":True,"polygon":{"type":"Polygon","coordinates":[ring]},
                  "review":{"status":"approved","date":"2026-11-07","evidence":f'Thomas explicitly approved K{site["number"]:02d} v{site["version"]}; real route evidence in review-batch-01-routes.json.'},"movements":[]}
        junction["excludedApproaches"]=site["review"].get("excludedApproaches",[])
        evidence={"id":site["id"],"geometryRevision":site["version"],"gates":{},"movements":[]}
        for arm,labels in ARMS.items():
            evidence["gates"][arm]={}
            for kind,label in zip(("entry","exit"),labels):
                g=gates[label]
                try:evidence["gates"][arm][kind]=dict(g,sample=endpoint(g,edges,kind,ring,
                    15 if site["id"]=="nymphenburger-waisenhaus" and arm=="south" else 45))
                except ValueError as error:evidence["gates"][arm][kind]=dict(g,error=str(error))
        for arm in ARMS:
            for kind,target in [("left",LEFT[arm]),("straight",STRAIGHT[arm]),("right",RIGHT[arm])]:
                identifier=f'{arm}-{target}-{kind}';item={"id":identifier,"enabled":False}
                try:
                    before=evidence["gates"][arm]["entry"];after=evidence["gates"][target]["exit"]
                    if "error" in before or "error" in after:raise ValueError(before.get("error",after.get("error")))
                    coord=lambda p:f'{p[0]:.9f},{p[1]:.9f}'
                    url=f'https://api.radlnavi.munichways.de/route/v1/bike/{coord(before["sample"])};{coord(after["sample"])}?steps=true&overview=full&geometries=geojson&annotations=nodes%2Cdistance&alternatives=false'
                    filename=f'{site["id"]}-{identifier}.json';payload=fetch(url,FIXTURES/filename,manifest,args.collect)
                    item.update(fixture=filename,url=url)
                    if payload.get("code")!="Ok":raise ValueError(f'Routing response {payload.get("code")}')
                    if any(w["distance"]>5 for w in payload["waypoints"]):
                        # The endpoint may be on a permitted parallel cycle path outside
                        # the polygon. Verify the ENTIRE returned route first, then query
                        # those exact network coordinates. Gate tolerances stay unchanged.
                        corridor_check(payload["routes"][0]["geometry"]["coordinates"],edges)
                        snapped=[w["location"] for w in payload["waypoints"]]
                        if any(inside(p,ring) for p in snapped):raise ValueError("Snapped endpoint inside polygon")
                        url=f'https://api.radlnavi.munichways.de/route/v1/bike/{coord(snapped[0])};{coord(snapped[1])}?steps=true&overview=full&geometries=geojson&annotations=nodes%2Cdistance&alternatives=false'
                        filename=f'{site["id"]}-{identifier}-network-endpoints.json'
                        payload=fetch(url,FIXTURES/filename,manifest,args.collect)
                        item.update(fixture=filename,url=url,endpointAdjustment="Exact verified legal network coordinate outside the polygon")
                        if payload.get("code")!="Ok" or any(w["distance"]>5 for w in payload["waypoints"]):raise ValueError("Exact network endpoint still snaps over 5m")
                    line=payload["routes"][0]["geometry"]["coordinates"];hits=crossings(line,ring)
                    if len(hits)!=2:raise ValueError("Route does not cross polygon exactly once")
                    entry,exit=hits
                    if meters(entry["location"],before["location"])>2.5:raise ValueError("Wrong entry gate")
                    if meters(exit["location"],after["location"])>2.5:raise ValueError("Wrong exit gate")
                    if kind=="right":
                        item["verified"]=True
                    else:
                        start,end=entry["geometrySegmentIndex"],exit["geometrySegmentIndex"]
                        corridor=[entry["location"],*line[start+1:end+1],exit["location"]]
                        supported=corridor_check(corridor,edges)
                        heading_distance=40 if site["id"]=="westend-zschokke" else 10
                        movement={"id":identifier,"enabled":True,"movement":kind,"entryArm":arm,"exitArm":target,
                                  "entry":entry["location"],"exit":exit["location"],"corridor":corridor,
                                  "approach":[point_at(line,max(0,entry["distanceAlongLegMeters"]-heading_distance)),entry["location"]],
                                  "departure":[exit["location"],point_at(line,exit["distanceAlongLegMeters"]+heading_distance)],
                                  "review":{"status":"approved","date":"2026-11-07","evidence":f'Reviewed geometry and legal directed OSM corridor; real route batch-01/{filename}.'}}
                        mx=cos(radians(entry["location"][1]))
                        heading=lambda path:degrees(atan2(path[-1][1]-path[0][1],(path[-1][0]-path[0][0])*mx))
                        turn=(heading(movement["departure"])-heading(movement["approach"])+180)%360-180
                        actual="straight" if abs(turn)<=30 else "left" if 45<=turn<=135 else None
                        item["turnDegrees"]=round(turn,2)
                        if actual is None:raise ValueError("Real arm direction is not an unambiguous left/straight movement")
                        item["logicalCandidate"]=kind
                        movement["movement"]=actual;movement["id"]=f'{arm}-{target}-{actual}';item["id"]=movement["id"]
                        test=dict(proposed,junctions=[dict(junction,movements=[movement])]);validate_catalog(test)
                        with patch("src.big_junctions.catalog",return_value=test):matched=add_guidance(payload)
                        if not matched:raise ValueError("Route fails production continuity/mode/corridor checks")
                        original=deepcopy(payload);matched["routes"][0].pop("guidance")
                        if matched!=original:raise ValueError("Guidance changed routing data")
                        junction["movements"].append(movement);item.update(enabled=True,verifiedCyclingWayIds=supported)
                except (ValueError,AssertionError,KeyError,IndexError,TypeError,HTTPError,TimeoutError) as error:
                    item["reason"]=str(error)
                    if kind!="right":junction["movements"].append({"id":identifier,"enabled":False,"movement":kind,
                        "entryArm":arm,"exitArm":target,"review":{"status":"unverified","evidence":str(error)}})
                if kind=="right":report["rightTurnChecks"].append(dict(item,junctionId=site["id"]))
                else:evidence["movements"].append(item)
                print(f'{site["id"]} {identifier}: {"verified" if item.get("enabled") or item.get("verified") else item.get("reason")}',flush=True)
        junction["enabled"]=any(m["enabled"] for m in junction["movements"])
        proposed["junctions"].append(junction);report["junctions"].append(evidence)
    validate_catalog(proposed)
    # Every real right-turn control must remain without optional guidance.
    for item in report["rightTurnChecks"]:
        if "fixture" not in item:continue
        payload=json.loads((FIXTURES/item["fixture"]).read_text(encoding="utf-8"))
        with patch("src.big_junctions.catalog",return_value=proposed):matched=add_guidance(payload)
        if matched is not None:raise ValueError(f'Right-turn control matched guidance: {item["fixture"]}')
    (ROOT/"review-batch-01-proposed-catalog.json").write_text(json.dumps(proposed,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (ROOT/"review-batch-01-routes.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f'Validated {sum(m["enabled"] for j in proposed["junctions"] for m in j["movements"])} total movements; runtime catalog unchanged.',flush=True)


if __name__=="__main__":main()
