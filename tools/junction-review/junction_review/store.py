"""File-based projects: immutable imports, separate edits, explicit decisions."""
from copy import deepcopy
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from threading import RLock

from .geometry import relocate_gates
from .model import STATUSES, digest, effective_site, geometry_fingerprint, validate_dataset, validate_site


class Conflict(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=path.name, suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class ProjectStore:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.lock = RLock()

    def _read(self):
        path = self.directory / 'project.json'
        if not path.exists():
            raise ValueError('Projekt fehlt. Zuerst eine Bildrunde importieren.')
        project = json.loads(path.read_text(encoding='utf-8'))
        dataset = json.loads((self.directory / 'imports' / (project['dataset'] + '.json')).read_text(encoding='utf-8'))
        return project, dataset

    def import_dataset(self, dataset, refresh=False):
        validate_dataset(dataset)
        with self.lock:
            identity = digest(dataset)
            path = self.directory / 'project.json'
            state = dict(schemaVersion=1, dataset=identity, sites={})
            if path.exists():
                state, old = self._read()
                if old['project']['id'] != dataset['project']['id']:
                    raise Conflict('In diesem Verzeichnis liegt ein anderes Projekt.')
                if state['dataset'] == identity:
                    return False
                if not refresh:
                    raise Conflict('Import geändert. Explizit --refresh verwenden; bisherige Daten bleiben erhalten.')
                old_by_id = {s['id']: s for s in old['sites']}
                new_ids = {s['id'] for s in dataset['sites']}
                if set(old_by_id) - new_ids:
                    raise Conflict('Ein Refresh darf bestehende Kreuzungen nicht entfernen. Neues Projekt für Teilmengen anlegen.')
                for base in dataset['sites']:
                    previous = old_by_id.get(base['id'])
                    if previous and previous['sourceFingerprint'] != base['sourceFingerprint']:
                        edit = state['sites'].setdefault(base['id'], {})
                        before = effective_site(previous, edit)
                        edit.setdefault('history', []).append(dict(at=now(), action='source-refresh',
                            previousGeometry={k: before[k] for k in ('polygon', 'gates', 'geometryRevision')},
                            previousDecision=before['decision'], previousSource=previous['sourceFingerprint']))
                        edit.pop('geometry', None)
                        edit['version'] = before['editVersion'] + 1
                        edit['geometryRevision'] = max(before['geometryRevision'] + 1, base['geometryRevision'])
                state['dataset'] = identity
            # The active pointer and edits are committed together only after the immutable import exists.
            archive = self.directory / 'imports' / (identity + '.json')
            if not archive.exists():
                atomic_write(archive, dataset)
            atomic_write(path, state)
            return True

    def snapshot(self):
        with self.lock:
            project, dataset = self._read()
            return dict(project=dataset['project'], source=dataset['source'],
                sites=[effective_site(s, project['sites'].get(s['id'], {})) for s in dataset['sites']])

    def carry_edits(self, other):
        """Explicitly preserve local work when expanding a pilot into a full project."""
        with other.lock:
            previous, source = other._read()
        with self.lock:
            project, dataset = self._read()
            old = {s['id']: s for s in source['sites']}
            new = {s['id']: s for s in dataset['sites']}
            count = 0
            for site_id, edit in previous['sites'].items():
                if not edit.get('decision') and not edit.get('geometry'):
                    continue
                if site_id not in new or old[site_id]['sourceFingerprint'] != new[site_id]['sourceFingerprint']:
                    raise Conflict('Lokale Prüfung mit abweichender Quelle separat erhalten: ' + site_id)
                existing = project['sites'].get(site_id)
                if existing and existing != edit:
                    raise Conflict('Beide Projekte haben Änderungen; getrennt erhalten: ' + site_id)
                if not existing:
                    project['sites'][site_id] = deepcopy(edit)
                    count += 1
            if count:
                atomic_write(self.directory / 'project.json', project)
            return count

    def import_technical(self, report):
        if report.get('status') != 'complete' or report.get('runtimeModified') is not False:
            raise ValueError('Nur abgeschlossene, nicht aktivierende Prüfberichte übernehmen.')
        with self.lock:
            project, dataset = self._read()
            bases = {s['id']: s for s in dataset['sites']}
            changed = 0
            for record in report['junctions']:
                base = bases[record['id']]
                edit = project['sites'].setdefault(record['id'], {})
                site = effective_site(base, edit)
                binding = record['reviewBinding']
                if site['status'] != 'confirmed' or not site['decisionCurrent'] or any(binding[k] != site[k] for k in ('geometryFingerprint', 'sourceFingerprint')):
                    raise Conflict('Prüfbericht passt nicht mehr zur bestätigten Geometrie: ' + record['id'])
                report_hash = digest(record)
                if edit.get('technicalReportFingerprint') == report_hash:
                    continue
                moves = record['movements']
                attempts = [m for m in moves if m['kind'] in ('left', 'straight')]
                passed = sum(bool(m.get('enabled')) for m in attempts)
                edit['technicalEvidence'] = dict(**binding,
                    technical=f'{passed}/{len(attempts)} Links-/Geradeausbeziehungen technisch bestanden',
                    deployment='Technisch geprüft · noch nicht aktiviert / deployed', deploymentStatus='not-live',
                    liveMovements=0, rechecks=[], movements=deepcopy(moves), fieldTests=[],
                    branchMovements=0, checkedAt=report.get('completedAt'), backendVersion=None,
                    normalGuidanceGates=record.get('normalGuidanceGates', []), logicalArms=record.get('logicalArms', {}))
                edit['technicalReportFingerprint'] = report_hash
                edit['version'] = site['editVersion'] + 1
                edit.setdefault('history', []).append(dict(at=now(), action='technical-check', reportFingerprint=report_hash))
                changed += 1
            if changed:
                atomic_write(self.directory / 'project.json', project)
            return changed

    def save(self, site_id, payload, preview=False):
        with self.lock:
            project, dataset = self._read()
            base = next((s for s in dataset['sites'] if s['id'] == site_id), None)
            if base is None:
                raise KeyError(site_id)
            state = deepcopy(project['sites'].get(site_id, {}))
            current = effective_site(base, state)
            if type(payload.get('expectedVersion')) is not int or payload['expectedVersion'] != current['editVersion']:
                raise Conflict('Inzwischen geändert. Ansicht neu laden, bevor du speicherst.')
            edited = deepcopy(current)
            if 'polygon' in payload and payload['polygon'] != current['polygon']:
                if current.get('geometryMode', 'editable') != 'editable':
                    raise ValueError('Für diesen Fall liegt noch keine bearbeitbare Geometrie vor.')
                edited['polygon'] = payload['polygon']
                edited['gates'] = relocate_gates(current, edited['polygon'])
                validate_site(edited)
            changed = geometry_fingerprint(edited) != current['geometryFingerprint']
            if changed:
                state['geometry'] = {k: edited[k] for k in ('polygon', 'gates')}
                state['geometryRevision'] = current['geometryRevision'] + 1
            if preview:
                return effective_site(base, state)
            status = payload.get('status')
            if status is not None:
                if status not in STATUSES:
                    raise ValueError('Unbekannter Prüfstatus.')
                if status == 'confirmed' and current.get('geometryMode', 'editable') == 'none':
                    raise ValueError('Ohne Geometrie ist keine Sichtfreigabe möglich. Zuerst Fläche und Anschlüsse vorbereiten.')
                note = payload.get('note', '').strip()
                if len(note) > 10000:
                    raise ValueError('Kommentar zu lang.')
                if status in ('deferred', 'excluded') and not note:
                    raise ValueError('Bitte einen kurzen Grund angeben.')
                deferred_until = payload.get('deferredUntil') or None
                if deferred_until:
                    date.fromisoformat(deferred_until)
                    if status != 'deferred':
                        raise ValueError('Wiedervorlage gehört zum Status Zurückgestellt.')
                state['decision'] = dict(status=status, note=note, deferredUntil=deferred_until,
                    at=now(), geometryFingerprint=geometry_fingerprint(edited), sourceFingerprint=base['sourceFingerprint'])
            elif not changed:
                raise ValueError('Keine Änderung zum Speichern.')
            state['version'] = current['editVersion'] + 1
            state.setdefault('history', []).append(dict(at=now(), action='geometry-and-decision' if changed and status else (
                'geometry' if changed else 'decision'), previousGeometryFingerprint=current['geometryFingerprint'],
                previousDecision=current['decision'], geometryFingerprint=geometry_fingerprint(edited),
                previousGeometry={k: current[k] for k in ('polygon', 'gates', 'geometryRevision')} if changed else None,
                decision=deepcopy(state.get('decision')) if status else None))
            project['sites'][site_id] = state
            atomic_write(self.directory / 'project.json', project)
            return effective_site(base, state)
