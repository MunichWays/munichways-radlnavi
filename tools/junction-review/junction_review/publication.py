"""Explicit, small public read-only snapshot; never publish project state/files."""
from copy import deepcopy
from datetime import datetime, timezone

from .districts import _districts

SCHEMA_VERSION = 2


def _inside(point, ring):
    x, y = point
    result = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            result = not result
    return result


def district_for(point):
    """Munich district containing a junction centre, from the bundled RadlNavi boundaries."""
    for number, feature in _districts().items():
        for polygon in feature['geometry']['coordinates']:
            if _inside(point, polygon[0]) and not any(_inside(point, hole) for hole in polygon[1:]):
                name = feature['properties']['name']
                return dict(id=number, name=name.split(' ', 1)[1] if name[:2].isdigit() else name)
    return None


def _public_site(site, city):
    evidence = site.get('evidence', {}) if site['evidenceCurrent'] else {}
    decision = site.get('decision') or {}
    district = district_for(site['origin'])
    return dict(id=site['id'], number=site['number'], name=site['name'],
        city='München' if district else city, district=district,
        origin=deepcopy(site['origin']), polygon=deepcopy(site['polygon']),
        gates=[{k:deepcopy(g[k]) for k in ('label','kind','location','forward','shared') if k in g}
               for g in site['gates']],
        status=site['status'], geometryRevision=site['geometryRevision'],
        note=decision.get('note') or site.get('note', ''), deferredUntil=decision.get('deferredUntil'),
        technical=site['technicalStatus'], deploymentStatus=site['deploymentStatus'],
        deployment=evidence.get('deployment', 'Kein verifizierter Live-Stand'),
        backendVersion=evidence.get('backendVersion'), branchMovements=evidence.get('branchMovements', 0),
        liveMovements=evidence.get('liveMovements', 0),
        movements=[{k:deepcopy(m[k]) for k in ('entryLabel','exitLabel','kind','enabled','reason','failureStage') if k in m}
                   for m in evidence.get('movements', [])],
        rechecks=[{k:deepcopy(r[k]) for k in ('entry','exit','date','reason') if k in r}
                  for r in evidence.get('rechecks', [])])


def public_snapshot(snapshot, *more, name=None):
    """One or more project snapshots; only K-numbered junctions are published.

    Unnumbered local candidates (project-specific P numbers) would collide
    between district projects and are left out of the public map.
    """
    snapshots = (snapshot, *more)
    sites, numbers = [], set()
    for item in snapshots:
        city = item['project'].get('city') or 'Ohne Stadt'
        for site in item['sites']:
            if site.get('number') is None:
                continue
            if site['number'] in numbers:
                raise ValueError(f"K{site['number']} kommt in mehreren Projekten vor.")
            numbers.add(site['number'])
            sites.append(_public_site(site, city))
    osm = [s['source'].get('osmRetrievedAt') for s in snapshots if s['source'].get('osmRetrievedAt')]
    return dict(schemaVersion=SCHEMA_VERSION, readOnly=True,
        projectName=name or (snapshot['project']['name'] if not more else 'Kreuzungsprüfung München'),
        publishedAt=datetime.now(timezone.utc).isoformat(),
        osmRetrievedAt=max(osm) if osm else None,
        sites=sorted(sites, key=lambda s:s['number']))
