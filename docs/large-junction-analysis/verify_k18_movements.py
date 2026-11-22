"""K18 v5: Gunther path/carriageway share one arm; Entry-5 is excluded."""
import argparse
from math import atan2, degrees
from unittest.mock import patch
import verify_ba01_movements as review


def run(collect=False):
    root = review.ROOT
    review.NUMBERS = {18}
    review.SOURCE = root / 'review-batch-03-ba09-remaining-images/review-data.json'
    review.FIXTURES = root.parents[1] / 'backend/tests/fixtures/big-junctions/k18-v5'
    review.REPORT = root / 'review-k18-v5-routes.json'
    review.MANIFEST = root / 'review-k18-v5-route-requests.json'
    review.PROPOSAL = root / 'review-k18-proposed-catalog.json'
    review.SUMMARY = root / 'review-k18-technical.md'
    review.TITLE = 'K18 v5 · Romanplatz Süd'
    review.REGION = 'BA09'
    review.REVIEW_DATE = '2026-11-16'
    original_configure = review.configure
    original_sample = review.check.gate_sample
    original_plan = review.check.plan

    def configure(sites):
        for site in sites:
            site['proposedLogicalArms'] = {
                arm: gates['entries'] + gates['exits']
                for arm, gates in site['review']['proposedLogicalArms'].items()}
        original_configure(sites)

    def gate_sample(gate, edges, ring):
        if gate['osmWayId'] == 1300636865 and gate['kind'] == 'entry':
            # Start after the upstream cycle-path branch. A 45m start changes
            # to Entry-2; this real 15m carriageway segment tests Entry-3 itself.
            return dict(sample=review.check.endpoint(gate, edges, 'entry', ring, 15),
                        distanceMeters=15, reason='After upstream Gunther cycle-path branch; preserve Entry-3 evidence')
        return original_sample(gate, edges, ring)

    def plan(site):
        tasks, samples = original_plan(site)
        gate = next(g for g in site['gates'] if g['label'] == 'Entry-3')
        heading = round(degrees(atan2(gate['forward'][0], gate['forward'][1]))) % 360
        for item in tasks:
            if item['entryLabel'] == 'Entry-3' and 'url' in item:
                # The reference represents a rider already approaching north;
                # do not let an unconstrained departure start with a U-turn.
                item['url'] += f'&bearings={heading},25;'
                item['referenceHeadingDegrees'] = heading
        return tasks, samples

    with patch.object(review, 'configure', configure), patch.object(review.check, 'gate_sample', gate_sample), patch.object(review.check, 'plan', plan):
        review.run(collect)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true')
    run(parser.parse_args().collect)
