"""Conservative cross-project identity matching, independent of review status."""
import re


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
    nodes = node_ids(site)
    for project_id, other in existing:
        if site['id'] == other['id'] or nodes & node_ids(other):
            return dict(projectId=project_id, siteId=other['id'], name=other['name'])
    return None
