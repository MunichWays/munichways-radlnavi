"""Technical proposal for app-approved K48-K50; K47 permanently excluded."""
import argparse
from copy import deepcopy
from unittest.mock import patch

import verify_ba01_movements as review

ROOT = review.ROOT
SOURCE = ROOT / 'review-batch-09-nine-lanes-images/review-data.json'
REPORT = ROOT / 'review-batch-09-nine-lanes-routes.json'


def technical_source():
    data = review.read(SOURCE)
    for site in data['sites']:
        if site['number'] == 48:
            # Four road continuations clockwise. The eastern park connection
            # remains in the approved geometry and is tested as ordinary-only.
            site['proposedLogicalArms'] = {
                'northeast': ['Exit-1', 'Entry-5'],
                'southeast': ['Entry-2', 'Exit-3'],
                'southwest': ['Entry-3', 'Exit-4'],
                'northwest': ['Entry-4', 'Exit-5']}
            site['normalGuidanceGates'] = ['Entry-1', 'Exit-2']
        if site['number'] == 50:
            # Westbound Exit-4 is the reverse-side two-way path; Exit-5 is the
            # normal right-side path. Identical macros would not identify it.
            reason = ('Exit-4 fuehrt westwaerts auf den Zweirichtungsweg der linken Strassenseite; '
                      'Exit-5 auf die normale rechte Seite. Dieselbe Links-/Geradeausansage waere '
                      'mehrdeutig. Konservativ normale Hinweise fuer Exit-4 beibehalten.')
            site['excludedMovements'] = [dict(entryLabel=entry, exitLabel='Exit-4', reason=reason)
                                         for entry in ('Entry-1', 'Entry-2')]
    return data


def run(collect=False):
    data = technical_source()
    original_read = review.read
    with patch.multiple(review,
            NUMBERS={48, 49, 50}, SOURCE=SOURCE,
            FIXTURES=ROOT.parents[1] / 'backend/tests/fixtures/big-junctions/batch-09',
            REPORT=REPORT, MANIFEST=ROOT / 'review-batch-09-nine-lanes-route-requests.json',
            PROPOSAL=ROOT / 'review-batch-09-nine-lanes-proposed-catalog.json',
            SUMMARY=ROOT / 'review-batch-09-nine-lanes-technical.md',
            TITLE='K48-K50; K47 dauerhaft ausgeschlossen', REGION='Neun Fahrspuren', REVIEW_DATE='2026-11-20'), \
            patch.object(review, 'read', side_effect=lambda path: deepcopy(data) if path == SOURCE else original_read(path)):
        if collect:
            sites = [s for s in data['sites'] if s['number'] in (48, 49, 50)]
            review.configure(sites)
            manifest = original_read(review.MANIFEST) if review.MANIFEST.exists() else {}
            for site in sites:
                excluded = {(m['entryLabel'], m['exitLabel']) for m in site.get('excludedMovements', [])}
                for item in review.check.plan(site)[0]:
                    if (item['entryLabel'], item['exitLabel']) in excluded and 'url' in item:
                        payload, retrieved = review.check.collect(item, manifest, True)
                        if retrieved:
                            review.write(review.FIXTURES / item['fixture'], payload)
                            manifest[item['fixture']] = dict(url=item['url'], retrievedAt=retrieved)
            review.write(review.MANIFEST, manifest)
        review.run(collect)
    report = original_read(REPORT)
    approvals = {s['id']: s for s in original_read(ROOT / 'review-batch-09-nine-lanes-decisions.json')['sites']}
    for site in report['junctions']:
        decision = approvals[site['id']]['decision']
        site['reviewBinding'] = {key: decision[key] for key in ('geometryFingerprint', 'sourceFingerprint')}
        if site['number'] == 48:
            site['normalGuidanceGates'] = ['Entry-1', 'Exit-2']
    review.write(REPORT, report)
    summary = ROOT / 'review-batch-09-nine-lanes-technical.md'
    with summary.open('a', encoding='utf-8') as file:
        file.write('\nK48: 8 weitere reale Routen ueber Entry-1/Exit-2 bleiben ohne Makro. '
                   'K47 dauerhaft ausgeschlossen. Die 24 bestandenen Beziehungen sind nur ein Vorschlag; '
                   'keine Aktivierung oder Aenderung des Laufzeitkatalogs.\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true')
    run(parser.parse_args().collect)
