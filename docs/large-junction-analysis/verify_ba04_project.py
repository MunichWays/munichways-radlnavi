"""BA04 Schwabing-West: technical checks of the two confirmed project geometries.

Reuses the batch-12 district pipeline unchanged: frozen exact approvals, real
Standard routes, directed OSM corridors and complete-catalog checks. No
activation, runtime writes or geometry changes. Report numbers K108/K109 are
internal; the project keeps its own numbering until an explicit activation.
"""
import argparse
from copy import deepcopy
from unittest.mock import patch

import verify_ba01_ba03_project as batch

PREFIX = 'review-batch-14-ba04-project'
SOURCE = batch.ROOT / (PREFIX + '-approved.json')
REPORT = batch.ROOT / (PREFIX + '-routes.json')
FIXTURES = batch.FIXTURES.parent / 'batch-14'
SELECTED = {
    'area-8192789c4e8926dd': ['osm-junction-1955541', 'osm-junction-1955522'],
}
# Kurfürstenplatz: unchanged real routes run exactly on these Hohenzollernstraße
# carriageway pieces (tertiary, no cycling restriction; 155603792/158901372
# oneway=yes stays directed). Only segments fully inside the approval count.
INNER_ROADS = {
    'osm-junction-1955522': [30816875, 155603792, 158901372],
}
# Explicit human instruction decisions, kept as individual pair exclusions.
EXCLUDED = {
    'osm-junction-1955522': [dict(entryLabel='Entry-1', exitLabel='Exit-2',
        reason='Thomas 26.11.2026: Von der Belgradstraße links in die Hohenzollernstraße Ost '
               'gibt es real nicht; die Standardroute fährt über die Kaiserstraße. Normale Hinweise bleiben.')],
}


def run(freeze=False, collect=False, import_results=False):
    original = batch.checks.ambiguous_exits

    def ambiguous_exits(site):
        return original(site) + deepcopy(EXCLUDED.get(site['id'], []))

    with patch.multiple(batch, PREFIX=PREFIX, SOURCE=SOURCE, REPORT=REPORT, FIXTURES=FIXTURES,
            SELECTED=SELECTED, POLICIES={}, FIRST_REPORT_NUMBER=108,
            TITLE='BA04 Schwabing-West: Hohenzollernstraße/Schleißheimer Straße und Kurfürstenplatz',
            INNER_ROADS={**batch.INNER_ROADS, **INNER_ROADS}), \
            patch.object(batch.checks, 'ambiguous_exits', side_effect=ambiguous_exits):
        if freeze:
            batch.freeze()
        batch.run(collect, import_results)
        summary = batch.ROOT / (PREFIX + '-technical.md')
        with summary.open('a', encoding='utf-8') as stream:
            stream.write('\n## BA04-Hinweise\n\n'
                '- Hohenzollernstraße/Schleißheimer Straße v3: Entry-3 liegt auf der Fahrbahn '
                '(OSM 486767219) etwa 4 m vor dem schrägen Radwegstück 486767220, analog zu Entry-4/Exit-4. '
                'Automatische Vierarmzuordnung ohne Sonderregel.\n'
                '- Kurfürstenplatz: innere Verbinder Hohenzollernstraße 30816875, 155603792, 158901372 '
                '(tertiary, ohne Radverbot; Einbahnrichtung bleibt gerichtet).\n'
                '- Kurfürstenplatz Entry-1 → Exit-2: ausdrücklich ausgeschlossen (Thomas).\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('freeze', 'collect', 'import-results'):
        parser.add_argument('--'+name, action='store_true')
    args = parser.parse_args()
    run(args.freeze, args.collect, args.import_results)
