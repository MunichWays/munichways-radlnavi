"""Verify approved K34-K37 against frozen real Standard routes; proposal only."""
import argparse
from unittest.mock import patch
import verify_ba01_movements as review


def run(collect=False):
    root = review.ROOT
    review.NUMBERS = {34, 35, 36, 37}
    review.SOURCE = root / 'review-batch-06-primary-images/review-data.json'
    review.FIXTURES = root.parents[1] / 'backend/tests/fixtures/big-junctions/batch-06'
    review.REPORT = root / 'review-batch-06-primary-routes.json'
    review.MANIFEST = root / 'review-batch-06-primary-route-requests.json'
    review.PROPOSAL = root / 'review-batch-06-primary-proposed-catalog.json'
    review.SUMMARY = root / 'review-batch-06-primary-technical.md'
    review.TITLE = 'K34-K37'
    review.REGION = 'Primary/Primary'
    review.REVIEW_DATE = '2026-11-16'
    review.run(collect)
    # Both halves must also work together on one unchanged, real route.
    report = review.read(review.REPORT)
    sites = {s['number']: s for s in report['junctions']}
    manifest = review.read(review.MANIFEST)
    combined = []
    for name, start_site, entry, end_site, exit in (
            ('west-east', 35, 'Entry-3', 37, 'Exit-2'),
            ('east-west', 37, 'Entry-1', 35, 'Exit-4')):
        start = sites[start_site]['gateEvidence'][entry]['sample']
        end = sites[end_site]['gateEvidence'][exit]['sample']
        coord = lambda p: f'{p[0]:.9f},{p[1]:.9f}'
        item = dict(fixture=f'combined-{name}.json',
            url='https://api.radlnavi.munichways.de/route/v1/bike/'
                + coord(start) + ';' + coord(end)
                + '?steps=true&overview=full&geometries=geojson&annotations=nodes%2Cdistance&alternatives=false&variant=standard')
        payload, retrieved = review.check.collect(item, manifest, collect)
        if retrieved:
            review.write(review.FIXTURES / item['fixture'], payload)
            manifest[item['fixture']] = dict(url=item['url'], retrievedAt=retrieved)
        with patch('src.big_junctions.catalog', return_value=review.read(review.PROPOSAL)):
            result = review.check.add_guidance(payload)
        if result is None:
            raise ValueError('Combined route rejected: ' + name)
        hits = result['routes'][0].pop('guidance')['junctions']
        expected = [sites[n]['id'] for n in (start_site, end_site)]
        if ([h['id'] for h in hits] != expected
                or any(h['movement'] != 'straight' for h in hits) or result != payload):
            raise ValueError('Combined route classification/data mismatch: ' + name)
        combined.append(dict(fixture=item['fixture'], verified=True, junctions=expected))
    report['combinedRouteChecks'] = combined
    review.write(review.MANIFEST, manifest)
    review.write(review.REPORT, report)
    with review.SUMMARY.open('a', encoding='utf-8') as file:
        file.write('\nBeide Teilkreuzungen gemeinsam: zwei echte durchgehende Standardrouten '
                   '(West/Ost und Ost/West), jeweils zwei korrekte Geradeaus-Makros; Routendaten unverändert.\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true')
    run(parser.parse_args().collect)
