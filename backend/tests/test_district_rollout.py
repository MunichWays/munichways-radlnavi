"""Current district activation retains both reviewed K46 cycling corridors."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from src.big_junctions import add_guidance, catalog, validate_catalog


class DistrictRolloutTests(unittest.TestCase):
    def test_k46_old_and_new_real_routes_produce_one_identical_instruction(self):
        root=Path(__file__).parent/'fixtures/big-junctions'
        for batch in ('batch-08','batch-12'):
            with self.subTest(batch=batch):
                payload=json.loads((root/batch/'lane-candidate-428767-east-south-left-entry-2-exit-3.json').read_text(encoding='utf-8'))
                before=deepcopy(payload)
                result=add_guidance(payload)
                hit,=result['routes'][0].pop('guidance')['junctions']
                self.assertEqual((hit['id'],hit['movement']),('lane-candidate-428767','left'))
                self.assertEqual((payload,result),(before,before))

    def test_alternate_corridors_need_review_and_the_same_gates(self):
        for mutation in ('unreviewed','other-exit','wrong-type'):
            data=deepcopy(catalog())
            junction=next(j for j in data['junctions'] if j['id']=='lane-candidate-428767')
            move=next(m for m in junction['movements'] if m.get('alternateCorridors'))
            if mutation=='unreviewed':
                move['alternateCorridors'][0]['review']['status']='draft'
            elif mutation=='other-exit':
                move['alternateCorridors'][0]['coordinates'][-1]=[11.6,48.2]
            else:
                move['alternateCorridors']=[None]
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                validate_catalog(data)


if __name__=='__main__':
    unittest.main()
