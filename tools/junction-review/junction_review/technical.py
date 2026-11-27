"""RadlNavi technical check for one confirmed junction, started from the app.

The check runs as a separate process (repository script verify_app_site.py),
writes only into the project's technical/ folder and never activates or
deploys anything. The result is imported here, under the project lock and
bound to the exact approved geometry; a changed approval rejects the import.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from threading import Thread
import time

from .model import identifier
from .store import Conflict, atomic_write

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / 'docs/large-junction-analysis/verify_app_site.py'
LIVE_KEYS = ('deployment', 'deploymentStatus', 'liveMovements', 'branchMovements', 'backendVersion', 'fieldTests', 'rechecks')


def available():
    return SCRIPT.exists() and (REPO / 'backend/src/big_junctions.py').exists()


def eligible(site):
    if site['status'] != 'confirmed' or not site['decisionCurrent']:
        raise ValueError('Technische Prüfung erst nach gespeicherter Geometriebestätigung möglich.')
    if site.get('geometryMode', 'editable') != 'editable':
        raise ValueError('Für diesen Fall liegt keine bearbeitbare Geometrie vor.')


def run_check(store, site_id, progress=lambda text: None, cancelled=lambda: False, runner=None):
    if not available():
        raise ValueError('Die technische Prüfung braucht das RadlNavi-Repository (Backend und Prüfskripte).')
    site = next((s for s in store.snapshot()['sites'] if s['id'] == site_id), None)
    if site is None:
        raise KeyError(site_id)
    eligible(site)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = store.directory / 'technical' / f"{identifier(site_id)}-v{site['geometryRevision']}-{stamp}"
    (runner or _subprocess)(store.directory, site_id, out, progress, cancelled)
    if cancelled():
        raise InterruptedError('Abgebrochen. Nichts übernommen.')
    report = json.loads((out / 'check-routes.json').read_text(encoding='utf-8'))
    result = json.loads((out / 'result.json').read_text(encoding='utf-8'))
    return import_result(store, site_id, report, result, out)


def _subprocess(project, site_id, out, progress, cancelled):
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONPATH=os.pathsep.join(
        str(REPO / p) for p in ('docs/large-junction-analysis', 'tools/junction-review', 'backend')))
    process = subprocess.Popen([sys.executable, '-u', str(SCRIPT), '--project', str(project), '--site', site_id,
                                '--out', str(out)], cwd=REPO, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')

    def watch():
        while process.poll() is None:
            if cancelled():
                process.kill()
                return
            time.sleep(.5)
    Thread(target=watch, daemon=True).start()
    checked, tail = 0, []
    for line in process.stdout:
        line = line.rstrip()
        tail = (tail + [line])[-8:]
        if line.startswith('PHASE '):
            progress(line[6:])
        elif re.match(r'^K\d+ Entry-\d+ -> Exit-\d+', line):
            checked += 1
            progress(f'{checked} Fahrbeziehungen geprüft …')
    if process.wait() != 0 and not cancelled():
        raise ValueError('Technische Prüfung fehlgeschlagen: ' + ' · '.join(l for l in tail if l)[-600:])


def import_result(store, site_id, report, result, out):
    record = next(r for r in report['junctions'] if r['id'] == site_id)
    with store.lock:
        state, _ = store._read()
        previous = deepcopy(state['sites'].get(site_id, {}).get('technicalEvidence', {}))
        store.import_technical(dict(report, junctions=[record]))
        state, _ = store._read()
        edit = state['sites'][site_id]
        evidence = edit['technicalEvidence']
        if record.get('status') == 'blocked-topology':
            evidence['technical'] = 'Technisch zurückgestellt: ' + record['reason']
        if previous.get('deploymentStatus') == 'live':
            # A recheck documents evidence; it never withdraws or widens the live state.
            for key in LIVE_KEYS:
                if key in previous:
                    evidence[key] = previous[key]
            suffix = ' · neue technische Prüfung aktiviert keine weiteren Beziehungen'
            if not evidence['deployment'].endswith(suffix):
                evidence['deployment'] += suffix
        label = 'Standardfall, in der App fertig geprüft' if result['standard'] else \
            f"Sonderfall: {len(result['issues'])} Punkt(e) zur Nachbearbeitung"
        evidence['technical'] += ' · ' + label
        try:
            folder = str(out.relative_to(store.directory))
        except ValueError:
            folder = str(out)
        evidence['appCheck'] = dict(deepcopy(result), checkedAt=report.get('completedAt'), folder=folder)
        atomic_write(store.directory / 'project.json', state)
    return next(s for s in store.snapshot()['sites'] if s['id'] == site_id)


__all__ = ['available', 'eligible', 'run_check', 'import_result', 'Conflict']
