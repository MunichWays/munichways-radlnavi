"""Exercise junction guidance with only the sources copied into production."""
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


BACKEND = Path(__file__).resolve().parents[1]
FIXTURES = BACKEND / 'tests/fixtures/big-junctions'


class ProductionPackagingTest(unittest.TestCase):
    def test_production_sources_support_regular_and_sequence_guidance(self):
        with tempfile.TemporaryDirectory() as directory:
            staged = Path(directory)
            (staged / 'src').mkdir()
            for line in (BACKEND / 'Dockerfile').read_text().splitlines():
                if not line.startswith('COPY '):
                    continue
                parts = shlex.split(line)
                if parts[:1] == ['COPY'] and parts[-1] == '/opt/app/src/':
                    for source in parts[1:-1]:
                        shutil.copy2(BACKEND / source, staged / 'src')
            cases = [
                ('romanplatz-nord', 'review-updates-2026-11-14/romanplatz-nord-east-west-straight-entry-1-exit-4.json'),
                ('mars-pappenheim', 'review-updates-2026-11-14/mars-pappenheim-north-east-left-entry-4-exit-2.json'),
                ('thomasiusplatz', 'review-updates-2026-11-14/thomasiusplatz-wilram-entry-3-exit-5.json'),
            ]
            script = '''
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from src.big_junctions import catalog, add_guidance
catalog()
for identifier, filename in json.loads(sys.argv[3]):
    raw = json.loads((Path(sys.argv[2]) / filename).read_text(encoding='utf-8'))
    result = add_guidance(raw, sequence_guidance=True)
    assert result is not None, identifier
    hit, = result['routes'][0].pop('guidance')['junctions']
    assert hit['id'] == identifier, hit
    assert result == raw, 'Raw route changed'
'''
            result = subprocess.run(
                [sys.executable, '-I', '-c', script, str(staged), str(FIXTURES), json.dumps(cases)],
                cwd=staged, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
