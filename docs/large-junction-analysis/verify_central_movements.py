"""Verify approved K42-K46 with explicit right-only entry exclusions. Writes proposal only."""
import argparse
from unittest.mock import patch
import verify_ba01_movements as review


def run(collect=False):
    root = review.ROOT
    review.NUMBERS = {42, 43, 44, 45, 46}
    review.SOURCE = root / 'review-batch-08-central-images/review-data.json'
    review.FIXTURES = root.parents[1] / 'backend/tests/fixtures/big-junctions/batch-08'
    review.REPORT = root / 'review-batch-08-central-routes.json'
    review.MANIFEST = root / 'review-batch-08-central-route-requests.json'
    review.PROPOSAL = root / 'review-batch-08-central-proposed-catalog.json'
    review.SUMMARY = root / 'review-batch-08-central-technical.md'
    review.TITLE = 'K42-K46; K46 Entry-1 nur rechts; K44 Wiedervorlage ab 23.11.2026'
    review.REGION = 'Zentrale Kreuzungen'
    review.REVIEW_DATE = '2026-11-17'
    # Legal inner continuation to the southeast cycleway; no extra boundary gate.
    review.check.INTERNAL_ROADS[46] = [264964142]
    original_sample = review.check.gate_sample

    def sample(gate, edges, ring):
        # The outer K43 samples snap onto neighbouring ways. Shorter points
        # remain on the same legal frozen path, beyond the 10m direction margin.
        distance = {63532580: 25, 1041805698: 15}.get(gate['osmWayId'])
        if distance is None:
            return original_sample(gate, edges, ring)
        return dict(sample=review.check.endpoint(gate, edges, gate['kind'], ring, distance),
                    distanceMeters=distance,
                    selectionReason='K43: outer 35m sample snapped over 5m onto a neighbouring way; '
                                    'shorter directed path sample verified with the live Standard router.')

    with patch.object(review.check, 'gate_sample', side_effect=sample):
        review.run(collect)
    report = review.read(review.REPORT)
    proposal = review.read(review.PROPOSAL)
    record = next(s for s in report['junctions'] if s['number'] == 44)
    blocked = next(m for m in record['movements']
                   if (m['entryLabel'], m['exitLabel']) == ('Entry-3', 'Exit-1'))
    if not blocked.get('enabled'):
        blocked['diagnosis'] = dict(stage='route-selection',
            reason='Standardroute fährt zunächst auf der Marsstraße nach Südosten und über '
                   'Lämmerstraße/Hirtenstraße zurück in die Seidlstraße; mehrfache Flächenquerung '
                   'statt der vorgesehenen Linksbeziehung. Keine Links-Makroansage; '
                   'die zwei tatsächlich gefahrenen Geradeausquerungen bleiben gültig.')
        blocked['deferredUntil'] = '2026-11-23'
        blocked['recheckReason'] = 'Thomas hat except=bicycle an der OSM-Linksabbiegebeschraenkung ergaenzt; OSM und Routing fruehestens ab 23.11.2026 neu pruefen.'
        blocked['reason'] += '; ' + blocked['diagnosis']['reason'] + '; Wiedervorlage ab 23.11.2026 (OSM except=bicycle).'
        junction = next(j for j in proposal['junctions'] if j['id'] == record['id'])
        movement = next(m for m in junction['movements']
                        if (m.get('entryLabel'), m.get('exitLabel')) == ('Entry-3', 'Exit-1'))
        movement['disabledReason'] = blocked['reason']
        review.write(review.REPORT, report)
        review.write(review.PROPOSAL, proposal)
        with review.SUMMARY.open('a', encoding='utf-8') as file:
            file.write('\nK44 Entry-3 → Exit-1: ' + blocked['diagnosis']['reason'] + ' Wiedervorlage ab 23.11.2026: OSM except=bicycle.\n')
    record = next(s for s in report['junctions'] if s['number'] == 46)
    blocked = next(m for m in record['movements']
                   if (m['entryLabel'], m['exitLabel']) == ('Entry-3', 'Exit-4'))
    if not blocked.get('enabled'):
        blocked['diagnosis'] = dict(stage='legal-corridor', osmWayId=1017221653,
            reason='Standardroute verwendet den inneren Gehwegabschnitt 1017221653 ohne '
                   'belegte Fahrradfreigabe (kein bicycle=yes/designated im eingefrorenen OSM). '
                   'Keine Erweiterung des Radkorridors auf unbelegte Gehwege; normale Hinweise bleiben.')
        blocked['deferredUntil'] = '2026-11-23'
        blocked['recheckReason'] = ('Thomas hat die OSM-Linksabbiegebeschränkung um except=bicycle ergänzt. '
                                  'Ab 23.11.2026 OSM-Relation, Routing-Datenimport und tatsächliche '
                                  'Standardroute erneut prüfen; die historische Gehweg-Diagnose allein '
                                  'belegt nicht die Ursache der geänderten Routenwahl.')
        blocked['reason'] += '; ' + blocked['diagnosis']['reason'] + '; Wiedervorlage ab 23.11.2026 (OSM except=bicycle).'
        junction = next(j for j in proposal['junctions'] if j['id'] == record['id'])
        movement = next(m for m in junction['movements']
                        if (m.get('entryLabel'), m.get('exitLabel')) == ('Entry-3', 'Exit-4'))
        movement['disabledReason'] = blocked['reason']
        review.write(review.REPORT, report)
        review.write(review.PROPOSAL, proposal)
        with review.SUMMARY.open('a', encoding='utf-8') as file:
            file.write('\nK46 Entry-3 → Exit-4: ' + blocked['diagnosis']['reason'] + '\n'
                       'Thomas meldet eine ergänzte Fahrrad-Ausnahme an der OSM-Linksabbiegebeschränkung. '
                       'Wiedervorlage ab 23.11.2026; OSM-Relation und Routing-Datenimport prüfen, '
                       'dann dieselbe Standardroute erneut testen. Bis dahin deaktiviert.\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true')
    run(parser.parse_args().collect)
