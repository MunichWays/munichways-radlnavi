"""Explicit bridges. The application core never imports RadlNavi runtime code."""
from copy import deepcopy
import json
import hashlib
from pathlib import Path

from .geometry import inside
from .model import SCHEMA_VERSION, digest, validate_area, validate_dataset


def import_radlnavi(source, project_id, city, district='', area=None, numbers=None):
    validate_area(area)
    raw = Path(source).read_bytes()
    data = json.loads(raw)
    sites = []
    for original in data['sites']:
        if numbers and original['number'] not in numbers:
            continue
        if area and not inside(original['origin'], area['coordinates'][0]):
            continue
        gates = deepcopy(original['gates'])
        for gate in gates:
            gate['id'] = gate['label'].lower()
        sites.append(dict(id=original['id'], number=original['number'], name=original['name'],
            geometryRevision=original['version'], origin=original['origin'], polygon=original['polygon'],
            gates=gates, logicalArms=original.get('proposedLogicalArms', {}),
            ways=[dict(id=w['id'], tags=w['tags'], coordinates=[[p['lon'], p['lat']] for p in w['geometry']]) for w in original['ways']],
            note=original.get('note', ''), outgoingLanes=original.get('outgoingLaneTotal'),
            sourceFingerprint=digest({key: original.get(key) for key in (
                'origin', 'polygon', 'gates', 'ways', 'proposedLogicalArms',
                'onRoadWayIds', 'roadDirectionOverrides', 'excludedMovements')}),
            provenance=dict(adapter='radlnavi-review-v1', originalStatus=original['status'],
                            originalReview=original.get('review'), sourceId=original['id'])))
    if not sites:
        raise ValueError('Keine Kreuzungen für die Auswahl gefunden.')
    dataset = dict(schemaVersion=SCHEMA_VERSION,
        project=dict(id=project_id, city=city, district=district, area=area),
        source=dict(adapter='radlnavi-review-v1', filename=Path(source).name,
                    sha256=hashlib.sha256(raw).hexdigest(), osmRetrievedAt=data.get('osmRetrievedAt'),
                    attribution='© OpenStreetMap-Mitwirkende, ODbL'), sites=sites)
    validate_dataset(dataset)
    return dataset


def export_review(snapshot):
    """Routing-neutral handoff, never a production catalog or activation command."""
    approved = [s for s in snapshot['sites'] if s['status'] == 'confirmed' and s['decisionCurrent'] and s.get('geometryMode', 'editable') == 'editable']
    return dict(schemaVersion=SCHEMA_VERSION, kind='junction-geometry-review', project=snapshot['project'],
        source=snapshot['source'], requiresTechnicalValidation=True,
        sites=[{k: deepcopy(s[k]) for k in ('id', 'number', 'name', 'origin', 'polygon', 'gates',
                'logicalArms', 'geometryRevision', 'geometryFingerprint', 'sourceFingerprint', 'decision', 'constraints') if k in s}
               for s in approved])
