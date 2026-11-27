"""P2/P7 explicit instruction decisions and current K06/Lachnerstrasse routes."""
import argparse
from unittest.mock import patch

import verify_ba01_ba03_project as batch

PREFIX = 'review-batch-13-guidance-followups'
SOURCE = batch.ROOT / (PREFIX + '-approved-v2.json')
REPORT = batch.ROOT / (PREFIX + '-routes.json')
FIXTURES = batch.FIXTURES.parent / 'batch-13'
SELECTED = {
    'area-603b6d7ec04db77e': ['osm-junction-13353278127'],
    'area-8c7276beba7eaf73': ['osm-junction-618702506'],
    'munich': ['nymphenburger-waisenhaus'],
}


def run(freeze=False, collect=False, import_results=False):
    policies = batch.checks.review.read(batch.ROOT / 'review-batch-13-guidance-decisions.json')
    original_sample = batch.checks.review.check.gate_sample

    def sample(gate, edges, polygon):
        if gate['osmWayId'] == 152093782:
            # Every tested 12–45m reference snaps 7.5–8.2m onto a parallel
            # pushing-bike path. A longer natural Lachnerstrasse route follows
            # the approved street gate correctly. Stay on its directed graph.
            return dict(sample=batch.checks.review.check.endpoint(gate, edges, gate['kind'], polygon, 120),
                        distanceMeters=120,
                        selectionReason='K06: 12–45m references snap onto a parallel footway. '
                                        'Use a 120m connected legal Lachnerstrasse reference; '
                                        'approved gates and 10m runtime heading evidence remain unchanged.')
        return original_sample(gate, edges, polygon)

    with patch.multiple(batch, PREFIX=PREFIX, SOURCE=SOURCE, REPORT=REPORT, FIXTURES=FIXTURES,
            SELECTED=SELECTED, POLICIES=policies, TITLE='P2 Maximilianstraße, P7 Königsplatz und K06 Lachnerstraße',
            INNER_ROADS={**batch.INNER_ROADS, 'osm-junction-13353278127': [1455393266]}), \
            patch.object(batch.checks.review.check, 'gate_sample', side_effect=sample):
        if freeze:
            batch.freeze()
        batch.run(collect, import_results)
        summary = batch.ROOT / (PREFIX+'-technical.md')
        with summary.open('a', encoding='utf-8') as stream:
            stream.write('\n## K06: Ursache der fehlenden Lachnerstraßen-Ansagen\n\n'
                'Im mit dem produktiven Backend-Commit f8add936 übereinstimmenden Katalog sind '
                'alle vier Links-/Geradeausbeziehungen von/zu Lachnerstraße deaktiviert. '
                'Aktuelle längere Alltagsrouten treffen die freigegebenen Anschlüsse, erhalten live aber keine Makrometadaten. '
                'Kurze Referenzen zwischen 12 und 45 m schnappen etwa 7,5–8,2 m auf einen parallelen Gehweg '
                '(teilweise pushing bike). Der aktuelle OSM-Weg 152093782 entspricht dem eingefrorenen Straßenverlauf. '
                'Referenzen 120 m entlang derselben legal verbundenen Lachnerstraße bestehen dagegen alle Prüfungen: '
                '8/8 Links-/Geradeausbeziehungen, 4/4 Rechtskontrollen. '
                'Unveränderte Geometrie und unveränderte 5-m-Snappinggrenze; nur äußere Referenzpunkte geändert. '
                'Die vier zusätzlichen Beziehungen sind technisch bereit, aber noch nicht aktiviert.\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('freeze', 'collect', 'import-results'):
        parser.add_argument('--'+name, action='store_true')
    args = parser.parse_args()
    run(args.freeze, args.collect, args.import_results)
