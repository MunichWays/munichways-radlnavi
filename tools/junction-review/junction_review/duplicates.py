"""Conservative cross-project identity matching, independent of review status."""
import re
import unicodedata

from .geometry import distance


def _street_names(site):
    return frozenset(' '.join(unicodedata.normalize('NFKC', name).casefold().split())
                     for name in site.get('name', '').split('/') if name.strip())


def _same_legacy_junction(site, other):
    # Early RadlNavi imports have named IDs and no OSM candidate nodes. Only
    # bridge that missing identity with the complete street set and an almost
    # identical centre. Proximity alone must never merge neighbouring/split
    # crossings, nor override two explicit, different OSM identities.
    nodes, other_nodes = node_ids(site), node_ids(other)
    if bool(nodes) == bool(other_nodes):
        return False
    legacy = other if nodes else site
    if (legacy.get('provenance') or {}).get('adapter') not in (
            'radlnavi-overview-v1', 'radlnavi-review-v1'):
        return False
    names = _street_names(site)
    return (len(names) >= 2 and names == _street_names(other)
            and bool(site.get('origin')) and bool(other.get('origin'))
            and distance(site['origin'], other['origin']) <= 15)


def node_ids(site):
    result = set((site.get('preparation') or {}).get('candidateNodes', []))
    provenance = site.get('provenance') or {}
    for value in (site['id'], provenance.get('sourceId'), provenance.get('draftSourceId')):
        match = re.fullmatch(r'(?:osm-junction|lane-candidate)-(\d+)', value or '')
        if match:
            result.add(int(match[1]))
    exclusion = provenance.get('exclusion') or {}
    result.update(exclusion.get('referenceNodeIds', []))
    if exclusion.get('referenceNodeId'):
        result.add(exclusion['referenceNodeId'])
    return result


def duplicate_of(site, existing):
    existing = list(existing)
    nodes = node_ids(site)
    for project_id, other in existing:
        if site['id'] == other['id'] or nodes & node_ids(other):
            return dict(projectId=project_id, siteId=other['id'], name=other['name'])
    matches = [(project_id, other) for project_id, other in existing
               if _same_legacy_junction(site, other)]
    # Ambiguous legacy identities need review rather than an arbitrary owner.
    if len(matches) == 1:
        project_id, other = matches[0]
        return dict(projectId=project_id, siteId=other['id'], name=other['name'])
    return None
