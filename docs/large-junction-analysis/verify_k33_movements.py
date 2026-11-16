"""Verify K33 v2 using the shared BA01 pipeline; never modifies runtime data."""
import argparse
import verify_ba01_movements as review


def run(collect=False):
    root = review.ROOT
    review.NUMBERS = {33}
    review.SOURCE = root / 'review-batch-05-ba01-remaining-images/review-data.json'
    review.FIXTURES = root.parents[1] / 'backend/tests/fixtures/big-junctions/k33'
    review.REPORT = root / 'review-batch-05-k33-routes.json'
    review.MANIFEST = root / 'review-k33-route-requests.json'
    review.PROPOSAL = root / 'review-k33-proposed-catalog.json'
    review.SUMMARY = root / 'review-k33-technical.md'
    review.TITLE = 'K33 v2 · Sendlinger-Tor-Platz'
    review.run(collect)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true')
    run(parser.parse_args().collect)
