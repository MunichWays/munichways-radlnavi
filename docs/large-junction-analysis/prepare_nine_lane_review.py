"""Prepare the four remaining nine-lane candidates, K47-K50; no runtime changes."""
import argparse
from unittest.mock import patch

import prepare_central_review as batch
from prepare_central_review import ROOT, prepare as prepare_base

SOURCE = ROOT / 'review-batch-09-nine-lanes-osm.json.gz'
DRAFTS = ROOT / 'review-batch-09-nine-lanes-drafts.json'
OUT = ROOT / 'review-batch-09-nine-lanes-images'
SELECTION = [(47, 'lane-candidate-428687', 428687),
             (48, 'lane-candidate-564153', 564153),
             (49, 'lane-candidate-1956058', 1956058),
             (50, 'lane-candidate-564108', 564108)]


def prepare(record, ways):
    site = prepare_base(record, ways)
    site['district'] = 'München · Neun ausgehende Fahrspuren'
    return site


def run(collect=False):
    with patch.multiple(batch, SOURCE=SOURCE, DRAFTS=DRAFTS, OUT=OUT,
                        SELECTION=SELECTION, prepare=prepare):
        batch.main(collect_source=collect, title='K47–K50 · Neun ausgehende Fahrspuren',
                   selection_label='Die vier noch offenen Kandidaten mit jeweils neun ausgehenden Kfz-Fahrspuren laut Inventar.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true')
    run(parser.parse_args().collect)
