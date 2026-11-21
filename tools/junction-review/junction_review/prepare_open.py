"""Fill missing project drafts, without regenerating reviewed geometry."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from urllib.request import Request, urlopen

from .discovery import prepare
from .geometry import distance
from .model import digest
from .store import ProjectStore, atomic_write


def context_query(origin):
    lon, lat = origin
    dx, dy = 200 / (111320 * math.cos(math.radians(lat))), 200 / 111320
    return 'https://api.openstreetmap.org/api/0.6/map.json?bbox=' + ','.join(
        f'{v:.7f}' for v in (lon-dx, lat-dy, lon+dx, lat+dy))


def fetch_context(url):
    request = Request(url, headers={'User-Agent': 'MunichWays-JunctionReview/1.0 (local geometry review)'})
    with urlopen(request, timeout=30) as response:
        data = json.loads(response.read(40_000_001))
    nodes = {n['id']: n for n in data['elements'] if n['type'] == 'node'}
    for way in data['elements']:
        if way['type'] == 'way':
            # Map responses include the complete referenced nodes. Do not guess
            # missing coordinates or use clipped geometry.
            way['geometry'] = [dict(lon=nodes[n]['lon'], lat=nodes[n]['lat']) for n in way['nodes']]
    data['osm3s'] = dict(timestamp_osm_base=datetime.now(timezone.utc).isoformat())
    return data


def proposals(raw, site):
    lon, lat = site['origin']
    dx, dy = 100 / (111320 * math.cos(math.radians(lat))), 100 / 111320
    area = dict(type='Polygon', coordinates=[[[lon-dx,lat-dy],[lon+dx,lat-dy],
                [lon+dx,lat+dy],[lon-dx,lat+dy],[lon-dx,lat-dy]]])
    return prepare(raw, dict(area=area))


def match_proposal(site, candidates):
    node_id = int(site['id'].split('-')[-1]) if site['id'].split('-')[-1].isdigit() else None
    exact = [s for s in candidates if node_id in s['preparation']['candidateNodes']]
    if len(exact) == 1:
        return exact[0]
    names = set(site['name'].split(' / '))
    near = [s for s in candidates if distance(s['origin'], site['origin']) < 65
            and len(names.intersection(s['name'].split(' / '))) >= 2]
    return near[0] if len(near) == 1 else None


def reviewed_elsewhere(site, directory):
    matches = []
    for path in sorted(directory.parent.glob('*/project.json')):
        if path.parent.resolve() == directory.resolve():
            continue
        snapshot = ProjectStore(path.parent).snapshot()
        for other in snapshot['sites']:
            if (other['decisionCurrent'] and other['status'] != 'open' and other.get('origin')
                    and distance(site['origin'], other['origin']) < 45
                    and len(set(site['name'].split(' / ')) & set(other['name'].split(' / '))) >= 2):
                matches.append(dict(projectId=path.parent.name, siteId=other['id'], status=other['status'],
                    label=snapshot['project']['name'] + ' / ' + ('P' + str(other['priorityRank']) if other.get('priorityRank') else 'K' + str(other['number']) if other.get('number') else other['id']),
                    geometryFingerprint=other['geometryFingerprint'], sourceFingerprint=other['sourceFingerprint']))
    return matches


def prepare_missing(project, fetch=fetch_context, progress=print):
    store = ProjectStore(project)
    snapshot = store.snapshot()
    targets = [s for s in snapshot['sites'] if s['status'] == 'open'
               and s.get('geometryMode') == 'none' and s.get('origin')]
    report = dict(prepared=[], linked=[], unresolved=[], errors=[])
    cache = store.directory / 'preparation-cache'
    cache.mkdir(exist_ok=True)
    for index, site in enumerate(targets, 1):
        label = f'{index}/{len(targets)} {site["name"]}'
        try:
            linked = reviewed_elsewhere(site, store.directory)
            if linked:
                proposal = None
                raw = None
                issue = 'Bereits in anderem Projekt bearbeitet: ' + ', '.join(
                    f'{m["label"]} ({m["status"]})' for m in linked)
            else:
                query = context_query(site['origin'])
                path = cache / (digest(query) + '.json')
                if path.exists():
                    raw = json.loads(path.read_text(encoding='utf-8'))
                else:
                    raw = fetch(query)
                    # Reject failed/partial responses before freezing a cache entry.
                    if raw.get('remark') or not isinstance(raw.get('elements'), list):
                        raise ValueError('Unvollstaendige OSM-Antwort')
                    atomic_write(path, raw)
                candidates, rejected = proposals(raw, site)
                proposal = match_proposal(site, candidates)
                issue = '' if proposal and proposal.get('gates') else (
                    'Keine eindeutige bearbeitbare Geometrie. Manuelle Klaerung erforderlich. ' +
                    '; '.join(sorted({r['reason'] for r in rejected if distance(r['origin'],site['origin']) < 65})))
                if issue:
                    proposal = None
            # Re-read under lock: never replace an intervening edit or decision.
            with store.lock:
                state, dataset = store._read()
                current = next(s for s in store.snapshot()['sites'] if s['id'] == site['id'])
                if current['editVersion'] != site['editVersion'] or current['status'] != 'open' or current.get('geometryMode') != 'none':
                    raise ValueError('Fall inzwischen bearbeitet; nicht ersetzt')
                dataset = deepcopy(dataset)
                base = next(s for s in dataset['sites'] if s['id'] == site['id'])
                if proposal:
                    for key in ('polygon','gates','ways','logicalArms','geometryMode','preparation','sourceFingerprint'):
                        base[key] = deepcopy(proposal[key])
                    base['geometryRevision'] = max(current['geometryRevision'] + 1, 1)
                    base['osmRetrievedAt'] = raw.get('osm3s', {}).get('timestamp_osm_base')
                    dates = [dataset['source'].get('osmRetrievedAt'), base['osmRetrievedAt']]
                    dataset['source']['osmRetrievedAt'] = max(filter(None, dates), default=None)
                    base['note'] = (base.get('note', '').split('\nVorbereitung: ')[0] + '\nAutomatischer Entwurf: ' + proposal['note']).strip()
                    base.pop('preparationIssue', None)
                    base.pop('linkedReviews', None)
                    base.setdefault('provenance', {})['draftSourceId'] = proposal['id']
                    category = 'prepared'
                else:
                    base['preparationIssue'] = issue
                    base['linkedReviews'] = linked
                    base['note'] = (site.get('note', '').split('\nVorbereitung: ')[0] + '\nVorbereitung: ' + issue).strip()
                    category = 'linked' if linked else 'unresolved'
                store.import_dataset(dataset, refresh=True)
            report[category].append(dict(id=site['id'], name=site['name'], reason=issue))
            progress(label + ': ' + category, flush=True)
        except (ValueError, OSError, KeyError, TypeError) as error:
            report['errors'].append(dict(id=site['id'], name=site['name'], reason=str(error)))
            progress(label + ': FEHLER ' + str(error), flush=True)
        atomic_write(store.directory / 'preparation-report.json', report)
    sites = store.snapshot()['sites']
    report['projectSummary'] = dict(total=len(sites),
        open=sum(s['status'] == 'open' for s in sites),
        readyForGeometryReview=sum(s['status'] == 'open' and s.get('geometryMode') == 'editable' for s in sites),
        linked=sum(bool(s.get('linkedReviews')) for s in sites))
    atomic_write(store.directory / 'preparation-report.json', report)
    return report
