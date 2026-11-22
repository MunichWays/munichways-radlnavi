"""Explicit, small public read-only snapshot; never publish project state/files."""
from copy import deepcopy
from datetime import datetime, timezone


def public_snapshot(snapshot):
    sites = []
    for site in snapshot['sites']:
        evidence = site.get('evidence', {}) if site['evidenceCurrent'] else {}
        decision = site.get('decision') or {}
        sites.append(dict(id=site['id'], number=site['number'], name=site['name'],
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
                      for r in evidence.get('rechecks', [])]))
    return dict(schemaVersion=1, readOnly=True,
        projectName=snapshot['project']['name'], publishedAt=datetime.now(timezone.utc).isoformat(),
        osmRetrievedAt=snapshot['source'].get('osmRetrievedAt'),
        sites=sorted(sites, key=lambda s:s['number'] or 0))
