"""Activation must exactly equal the independently verified movement proposal."""
import json
from pathlib import Path
import unittest

from src.big_junctions import catalog


class MunichMapActivationTests(unittest.TestCase):
    def test_25_active_map_cases_preserve_all_32_movement_exclusions(self):
        root = Path(__file__).resolve().parents[2] / 'docs/large-junction-analysis'
        report = json.loads((root / 'review-batch-11-munich-project-routes.json').read_text(encoding='utf-8'))
        proposal = json.loads((root / 'review-batch-11-munich-project-proposed-catalog.json').read_text(encoding='utf-8'))
        actual = {j['id']: j for j in catalog()['junctions']}
        expected = {j['id']: j for j in proposal['junctions']}
        enabled = disabled = cases = 0
        for record in report['junctions']:
            if record.get('status') == 'blocked-topology':
                self.assertNotIn(record['id'], actual)
                continue
            junction = actual[record['id']]
            self.assertEqual(junction, expected[record['id']])
            verified = {m['id'] for m in record['movements'] if m.get('enabled') and m.get('verified')}
            self.assertEqual({m['id'] for m in junction['movements'] if m['enabled']}, verified)
            enabled += len(verified)
            disabled += sum(not m['enabled'] for m in junction['movements'])
            cases += 1
        self.assertEqual((cases, enabled, disabled), (25, 185, 32))
        self.assertNotIn('lane-candidate-26823592', actual)
