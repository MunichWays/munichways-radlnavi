"""Read-only migration adapter for the complete, existing RadlNavi overview."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

from .model import digest, geometry_fingerprint, validate_dataset


def import_overview(repository, project_id='munich', city='München'):
    root = Path(repository).resolve() / 'docs/large-junction-analysis'
    previous_path = list(sys.path)
    try:
        sys.path.insert(0, str(root))
        spec = importlib.util.spec_from_file_location('_radlnavi_overview_reader', root / 'organize_review_images.py')
        legacy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(legacy)
        overview = legacy.read_review_overview()
    finally:
        sys.path[:] = previous_path
    # Use the existing generic adapter for all cycling geometries; no new geometry.
    normalized = {}
    dates = []
    for batch in legacy.BATCHES:
        raw = json.loads((batch / 'review-data.json').read_text(encoding='utf-8'))
        dates.append(raw.get('osmRetrievedAt', ''))
        for original in raw['sites']:
            gates = deepcopy(original.get('gates', []))
            for gate in gates:
                gate['id'] = gate['label'].lower()
            normalized[original['id']] = dict(gates=gates,
                ways=[dict(id=w['id'], tags=w['tags'], coordinates=[[p['lon'], p['lat']] for p in w['geometry']]) for w in original.get('ways', [])],
                osmRetrievedAt=raw.get('osmRetrievedAt'))
    points = {f['properties']['osmNodeId']: f['geometry']['coordinates'] for f in json.loads((root / 'munich-review-queue.geojson').read_text(encoding='utf-8'))['features']}
    inventory = json.loads((root / 'outgoing-lanes-munich-inventory.json').read_text(encoding='utf-8'))['candidates']
    excluded = {d['junctionId']: d for d in json.loads((root / 'junction-review-decisions.json').read_text(encoding='utf-8'))['decisions']}
    catalog = {s['id']: s for s in overview['prepared']['junctions']}
    sites = []
    for group, records in overview['groups'].items():
        for original in records:
            source = normalized.get(original['id'], dict(gates=[], ways=[], osmRetrievedAt=None))
            polygon = original.get('polygon', [])
            origin = original.get('origin')
            if origin is None and polygon:
                origin = [sum(p[i] for p in polygon[:-1]) / (len(polygon) - 1) for i in (0, 1)]
            if origin is None:
                node_ids = set(original.get('candidateNodeIds', []))
                match = next((g for g in inventory if node_ids.intersection(g['nodeIds'])), None)
                origin = match['origin'] if match else points.get(excluded.get(original['id'], {}).get('referenceNodeId'))
            status = 'confirmed' if group == '1-bestaetigt' else ('excluded' if group == '3-ausgeschlossen' else 'open')
            review = original.get('review', {})
            if status == 'confirmed' and review.get('reviewedGeometrySha256'):
                evidence = dict(polygon=polygon, gates=[{k: g[k] for k in ('kind', 'location', 'osmWayId', 'label', 'forward')} for g in sorted(original['gates'], key=lambda g: g['label'])])
                if hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(',', ':')).encode()).hexdigest() != review['reviewedGeometrySha256']:
                    raise ValueError('Freigabe passt nicht zur importierten Geometrie: ' + original['id'])
            technical = overview['technical'].get(original['id'], {})
            phase = legacy.status_for(original, overview['state'], technical)
            moves = technical.get('movements', []) if technical.get('geometryRevision') == original['version'] else []
            site = dict(id=original['id'], number=original.get('number'), name=original['name'],
                geometryRevision=original['version'], origin=origin, polygon=polygon,
                geometryMode='editable' if polygon and source['gates'] else ('reference' if polygon else 'none'),
                gates=source['gates'], ways=source['ways'], logicalArms=original.get('proposedLogicalArms', {}),
                note=original.get('note', ''), outgoingLanes=original.get('outgoingLaneTotal'),
                district=original.get('district', ''), osmRetrievedAt=source['osmRetrievedAt'],
                provenance=dict(adapter='radlnavi-overview-v1', originalStatus=original['status'],
                    originalReview=review, sourceId=original['id'], legacyGroup=group,
                    exclusion=excluded.get(original['id'])),
                sourceFingerprint=digest({key: original.get(key) for key in (
                    'origin', 'polygon', 'gates', 'ways', 'proposedLogicalArms',
                    'onRoadWayIds', 'roadDirectionOverrides', 'excludedMovements')}),
                constraints={key: deepcopy(original.get(key, [] if key != 'roadDirectionOverrides' else {})) for key in ('onRoadWayIds', 'roadDirectionOverrides', 'excludedMovements')})
            fp = geometry_fingerprint(site)
            if status != 'open':
                site['importedDecision'] = dict(status=status, note=review.get('note') or site['note'],
                    deferredUntil=None, at=review.get('date'), origin='legacy-overview',
                    geometryFingerprint=fp, sourceFingerprint=site['sourceFingerprint'])
            rechecks = legacy.pending_rechecks(original, technical)
            site['constraints']['movementRechecks'] = deepcopy(rechecks)
            site['constraints']['movementExclusions'] = [deepcopy(m) for m in moves if m.get('kind') in ('left', 'straight') and not m.get('enabled')]
            site['constraints']['normalGuidanceGates'] = technical.get('normalGuidanceGates', [])
            branch = catalog.get(site['id'], {})
            site['evidence'] = dict(geometryFingerprint=fp, sourceFingerprint=site['sourceFingerprint'],
                technical=phase['technical'], deployment=phase['text'],
                deploymentStatus='live' if phase['css'] == 'live' else ('older-geometry' if phase['css'] == 'older' else 'not-live'),
                liveMovements=phase['liveMovements'], rechecks=rechecks,
                normalGuidanceGates=technical.get('normalGuidanceGates', []),
                logicalArms=technical.get('logicalArms', {}) if technical.get('geometryRevision') == original['version'] else {},
                movements=[{k: deepcopy(m[k]) for k in ('id', 'entryLabel', 'exitLabel', 'kind', 'enabled', 'reason', 'permanent', 'deferredUntil', 'recheckReason') if k in m} for m in moves],
                branchMovements=sum(bool(m.get('enabled')) for m in branch.get('movements', [])) if branch.get('enabled') else 0,
                fieldTests=[t for t in overview['field_tests'] if t.get('geometryRevisions', {}).get(site['id']) == original['version']],
                checkedAt=overview['state'].get('checkedAt'), backendVersion=overview['state'].get('version', {}).get('backend'))
            sites.append(site)
    source = dict(adapter='radlnavi-overview-v1', filename='kreuzungspruefung/index.html',
        sha256=digest(sites), osmRetrievedAt=max(filter(None, dates), default=None),
        attribution='© OpenStreetMap-Mitwirkende, ODbL',
        liveCheckedAt=overview['state'].get('checkedAt'), backendVersion=overview['state'].get('version', {}).get('backend'),
        cityScope=overview['scope'], legacyCounts={group: len(records) for group, records in overview['groups'].items()})
    dataset = dict(schemaVersion=1, project=dict(id=project_id, city=city, district='Gesamte Kreuzungsprüfung', area=None), source=source, sites=sites)
    validate_dataset(dataset)
    return dataset
