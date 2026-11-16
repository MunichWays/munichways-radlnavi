"""Verify approved K38/K40/K41; K39 stays excluded. Writes proposal only."""
import argparse
import verify_ba01_movements as review


def run(collect=False):
    root = review.ROOT
    review.NUMBERS = {38, 40, 41}
    review.SOURCE = root / 'review-batch-07-lanes-images/review-data.json'
    review.FIXTURES = root.parents[1] / 'backend/tests/fixtures/big-junctions/batch-07'
    review.REPORT = root / 'review-batch-07-lanes-routes.json'
    review.MANIFEST = root / 'review-batch-07-lanes-route-requests.json'
    review.PROPOSAL = root / 'review-batch-07-lanes-proposed-catalog.json'
    review.SUMMARY = root / 'review-batch-07-lanes-technical.md'
    review.TITLE = 'K38, K40, K41; K39 dauerhaft ausgeschlossen'
    review.REGION = 'Priorität nach Fahrspuren'
    review.REVIEW_DATE = '2026-11-16'
    review.run(collect)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true')
    run(parser.parse_args().collect)
