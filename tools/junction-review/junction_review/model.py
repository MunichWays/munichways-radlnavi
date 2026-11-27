"""Versioned interchange model shared by UI, imports and future routing adapters."""
from copy import deepcopy
import hashlib
import json
import math
import re

from .geometry import boundary_distance, point, ring

SCHEMA_VERSION = 1
STATUSES = {'open', 'confirmed', 'deferred', 'excluded'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,119}', value):
        raise ValueError('Ungültige stabile ID.')
    return value


def geometry_fingerprint(site):
    return digest({k: site[k] for k in ('polygon', 'gates', 'logicalArms')})


def validate_area(area):
    if area is not None:
        if not isinstance(area, dict) or area.get('type') != 'Polygon' or len(area.get('coordinates', [])) != 1:
            raise ValueError('Gebiet muss ein GeoJSON-Polygon ohne Löcher sein.')
        ring(area['coordinates'][0])


def validate_site(site):
    required = {'id', 'name', 'number', 'origin', 'geometryRevision', 'polygon', 'gates', 'ways', 'logicalArms', 'sourceFingerprint'}
    if not isinstance(site, dict) or not required <= site.keys():
        raise ValueError('Kreuzung unvollständig; Datenvertrag v1 beachten.')
    mode = site.get('geometryMode', 'editable')
    if mode not in ('editable', 'reference', 'none'):
        raise ValueError('Ungültiger Geometriemodus.')
    if not isinstance(site['gates'], list) or (not site['gates'] and mode == 'editable') or not isinstance(site['ways'], list) or not isinstance(site['logicalArms'], dict):
        raise ValueError('Anschlüsse, Wege oder Straßenarme fehlen.')
    if (site['number'] is not None and type(site['number']) is not int) or type(site['geometryRevision']) is not int or site['geometryRevision'] < (0 if mode == 'none' else 1):
        raise ValueError('Ungültige Kreuzungsnummer oder Geometrierevision.')
    if not isinstance(site['sourceFingerprint'], str) or not site['sourceFingerprint']:
        raise ValueError('Quellfingerprint fehlt.')
    identifier(site['id'])
    if site['origin'] is not None:
        point(site['origin'])
    if site['polygon']:
        ring(site['polygon'])
    elif mode != 'none':
        raise ValueError('Geometrie fehlt.')
    if not isinstance(site['name'], str) or not site['name'].strip():
        raise ValueError('Kreuzungsname fehlt.')
    ways = {str(w['id']): w for w in site['ways']}
    if len(ways) != len(site['ways']):
        raise ValueError('Doppelte OSM-Wege.')
    for way in ways.values():
        if len(way['coordinates']) < 2:
            raise ValueError('Weg ohne Geometrie.')
        for p in way['coordinates']:
            point(p)
    labels, ids = set(), set()
    for gate in site['gates']:
        identifier(gate['id'])
        if gate['label'] in labels or gate['id'] in ids:
            raise ValueError('Doppelte Anschluss-ID oder Beschriftung.')
        labels.add(gate['label'])
        ids.add(gate['id'])
        point(gate['location'])
        if gate['kind'] not in ('entry', 'exit') or str(gate['osmWayId']) not in ways:
            raise ValueError('Anschluss ohne belegten Weg oder Fahrtrichtung.')
        if boundary_distance(gate['location'], site['polygon']) > .3:
            raise ValueError('Anschlusspunkt liegt nicht auf der Flächengrenze.')
        if boundary_distance(gate['location'], ways[str(gate['osmWayId'])]['coordinates']) > .3:
            raise ValueError('Anschlusspunkt liegt nicht auf seinem OSM-Weg.')
        vector = gate.get('forward')
        if not isinstance(vector, list) or len(vector) != 2 or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in vector) or not .9 < math.hypot(*vector) < 1.1:
            raise ValueError('Richtungsevidenz des Anschlusses fehlt.')
    assigned = [label for labels in site['logicalArms'].values() for label in labels]
    if len(assigned) != len(set(assigned)) or not set(assigned) <= {g['label'] for g in site['gates']}:
        raise ValueError('Ungültige Zuordnung der Straßenarme.')


def validate_dataset(dataset):
    if not isinstance(dataset, dict) or not {'schemaVersion', 'project', 'source', 'sites'} <= dataset.keys():
        raise ValueError('Unvollständiges Projektformat.')
    if dataset['schemaVersion'] != SCHEMA_VERSION:
        raise ValueError('Unbekannte Datenformat-Version.')
    identifier(dataset['project']['id'])
    if not dataset['project']['city'].strip():
        raise ValueError('Stadt fehlt.')
    validate_area(dataset['project'].get('area'))
    if not isinstance(dataset['sites'], list) or (not dataset['sites'] and not dataset['source'].get('existingJunctions')):
        raise ValueError('Projekt enthält keine Kreuzungen.')
    ids = set()
    for site in dataset['sites']:
        validate_site(site)
        if site['id'] in ids:
            raise ValueError('Doppelte Kreuzungs-ID.')
        ids.add(site['id'])


def effective_site(base, state):
    site = deepcopy(base)
    override = state.get('geometry')
    if override:
        for key in ('polygon', 'gates', 'logicalArms'):
            if key in override:
                site[key] = deepcopy(override[key])
    fingerprint = geometry_fingerprint(site)
    decision = state.get('decision', base.get('importedDecision'))
    current = bool(decision and decision['geometryFingerprint'] == fingerprint and decision['sourceFingerprint'] == base['sourceFingerprint'])
    evidence = state.get('technicalEvidence', base.get('evidence', {}))
    if evidence:
        site['evidence'] = deepcopy(evidence)
    else:
        site.pop('evidence', None)
    evidence_current = evidence.get('geometryFingerprint') == fingerprint and evidence.get('sourceFingerprint') == base['sourceFingerprint']
    if evidence_current and state.get('technicalEvidence'):
        site.setdefault('constraints', {})['normalGuidanceGates'] = evidence.get('normalGuidanceGates', [])
        site['constraints']['technicalMovementExclusions'] = [deepcopy(m) for m in evidence.get('movements', []) if m.get('kind') in ('left', 'straight') and not m.get('enabled')]
    # Human pair exclusions (guidance decision, not geometry): used at the next
    # technical freeze and kept separate from the approval fingerprint.
    exclusions = state.get('movementExclusions', [])
    site['movementExclusions'] = deepcopy(exclusions)
    if exclusions:
        constraints = site.setdefault('constraints', {})
        known = {(m['entryLabel'], m['exitLabel']) for m in constraints.get('excludedMovements', [])}
        constraints['excludedMovements'] = deepcopy(constraints.get('excludedMovements', [])) + [
            dict(entryLabel=m['entryLabel'], exitLabel=m['exitLabel'], reason=m['reason'])
            for m in exclusions if (m['entryLabel'], m['exitLabel']) not in known]
    site.update(geometryFingerprint=fingerprint, editVersion=state.get('version', 0),
                geometryRevision=state.get('geometryRevision', base['geometryRevision']),
                decision=deepcopy(decision), decisionCurrent=current,
                status=decision['status'] if current else 'open',
                technicalStatus=evidence.get('technical', 'not-run') if evidence_current else 'not-run',
                deploymentStatus=evidence.get('deploymentStatus', 'unknown') if evidence_current else ('older-geometry' if evidence.get('liveMovements') else 'unknown'),
                evidenceCurrent=evidence_current,
                history=deepcopy(state.get('history', [])))
    if site['status'] == 'excluded':
        site['technicalStatus'] = 'Keine Aktivierung vorgesehen: ausgeschlossen'
        if evidence and evidence_current and site['deploymentStatus'] != 'live':
            site['evidence']['technical'] = site['technicalStatus']
            site['evidence']['deployment'] = 'Ausgeschlossen · nicht aktiviert / deployed'
    return site


def summarize(snapshot):
    """Compact automation report: no road geometries or full conversation needed."""
    counts = {status: 0 for status in sorted(STATUSES)}
    for site in snapshot['sites']:
        counts[site['status']] += 1
    return dict(project=snapshot['project'], total=len(snapshot['sites']), counts=counts,
        sites=[dict(id=s['id'], number=s['number'], geometryRevision=s['geometryRevision'], status=s['status'],
                    staleDecision=bool(s['decision'] and not s['decisionCurrent']),
                    technicalStatus=s['technicalStatus'], deploymentStatus=s['deploymentStatus'],
                    unassignedGates=sorted({g['label'] for g in s['gates']} - {label for group in s['logicalArms'].values() for label in group}
                        - ({label for group in s.get('evidence', {}).get('logicalArms', {}).values() for label in group} | set(s.get('evidence', {}).get('normalGuidanceGates', [])) if s['evidenceCurrent'] else set())),
                    deferredUntil=s['decision'].get('deferredUntil') if s['decisionCurrent'] else None)
               for s in sorted(snapshot['sites'], key=lambda s: s['number'] or 0, reverse=True)])
