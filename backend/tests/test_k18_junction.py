"""K18 activates verified approaches and preserves unverified carriageway pairs."""
import json
from pathlib import Path
import unittest

from src.big_junctions import add_guidance, catalog


class K18JunctionTest(unittest.TestCase):
    def test_approved_catalog_and_real_routes(self):
        junction = next(j for j in catalog()['junctions'] if j['id'] == 'romanplatz-sued')
        self.assertEqual(sum(bool(m.get('enabled')) for m in junction['movements']), 8)
        self.assertEqual({(m['entryLabel'], m['exitLabel']) for m in junction['movements'] if not m['enabled']},
                         {('Entry-3', 'Exit-1'), ('Entry-3', 'Exit-4')})
        root = Path(__file__).resolve().parents[2]
        record = json.loads((root / 'docs/large-junction-analysis/review-k18-v5-routes.json').read_text(encoding='utf-8'))['junctions'][0]
        self.assertFalse(any(m['entryLabel'] == 'Entry-5' for m in record['movements']))
        for item in record['movements']:
            payload = json.loads((Path(__file__).parent / 'fixtures/big-junctions/k18-v5' / item['fixture']).read_text(encoding='utf-8'))
            result = add_guidance(payload)
            with self.subTest(pair=item['id']):
                if item.get('enabled'):
                    hit, = result['routes'][0].pop('guidance')['junctions']
                    self.assertEqual((hit['id'], hit['movement'], hit['entryArm'], hit['exitArm']),
                                     (junction['id'], item['kind'], item['entryArm'], item['exitArm']))
                elif result:
                    hits = result['routes'][0].pop('guidance')['junctions']
                    self.assertFalse(any(h['occurrenceId'].startswith(junction['id']+':'+item['id']+':') for h in hits))
                if result:
                    self.assertEqual(result, payload)
