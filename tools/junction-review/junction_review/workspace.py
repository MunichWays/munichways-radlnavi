"""Project addressing and bounded background preparation, without a global active project."""
from copy import deepcopy
from pathlib import Path
from threading import Lock, Thread
import uuid

from .discovery import discover, selection_query
from .model import digest, identifier
from .store import Conflict, ProjectStore, atomic_write
from .osm_client import cancel_when
from .duplicates import duplicate_of
from . import technical


class Workspace:
    def __init__(self, default_store, prepare=discover):
        self.default = default_store
        self.root = default_store.directory.parent.resolve()
        self.prepare = prepare
        self.lock = Lock()
        self.jobs = {}
        self.working = set()
        self.stores = {default_store.directory.name: default_store}

    def store(self, project_id=None):
        if not project_id:
            return self.default
        directory = (self.root / identifier(project_id)).resolve()
        if directory.parent != self.root:
            raise ValueError('Projekt liegt außerhalb des Arbeitsverzeichnisses.')
        # All requests for one project must share its optimistic-write lock.
        with self.lock:
            return self.stores.setdefault(directory.name, ProjectStore(directory))

    def snapshot(self, store):
        return dict(**store.snapshot(), workspaceId=store.directory.name)

    def projects(self, current):
        result = []
        for path in sorted(self.root.glob('*/project.json')):
            try:
                store = self.store(path.parent.name)
                data = store.snapshot()
                result.append(dict(id=path.parent.name, name=data['project']['name'],
                                   count=len(data['sites']), active=store.directory == current.directory))
            except (ValueError, KeyError, OSError):
                continue
        return result

    def start(self, selection, source='auto'):
        selection_query(selection)  # Reject invalid geometry before creating a job.
        selection = deepcopy(selection)
        with self.lock:
            if self.working:
                raise Conflict('Eine OSM-Vorbereitung läuft noch. Nach einem Abbruch muss der laufende Abruf erst auslaufen; bitte kurz warten.')
            job_id = uuid.uuid4().hex
            self.jobs[job_id] = dict(id=job_id, kind='area', status='running', phase='OSM-Daten laden und Kreuzungen vorbereiten …')
            self.working.add(job_id)
            # Terminal jobs need not accumulate for the lifetime of the server.
            for old in list(self.jobs)[:-10]:
                if old not in self.working:
                    self.jobs.pop(old, None)
        Thread(target=self._run, args=(job_id, selection, source), daemon=True).start()
        return self.job(job_id)

    def job(self, job_id):
        with self.lock:
            return deepcopy(self.jobs[identifier(job_id)])

    def current(self, kind='area'):
        with self.lock:
            return next((deepcopy(j) for j in self.jobs.values()
                         if j['status'] == 'running' and j.get('kind', 'area') == kind), None)

    def start_technical(self, store, site_id, runner=None):
        site = next((s for s in store.snapshot()['sites'] if s['id'] == site_id), None)
        if site is None:
            raise KeyError(site_id)
        technical.eligible(site)
        if not technical.available():
            raise ValueError('Die technische Prüfung braucht das RadlNavi-Repository (Backend und Prüfskripte).')
        with self.lock:
            if any(j['status'] == 'running' and j.get('kind') == 'technical' for j in self.jobs.values()):
                raise Conflict('Es läuft bereits eine technische Prüfung. Bitte deren Ende abwarten.')
            job_id = uuid.uuid4().hex
            self.jobs[job_id] = dict(id=job_id, kind='technical', status='running', projectId=store.directory.name,
                                     siteId=site_id, phase='Technische Prüfung wird gestartet …')
            for old in list(self.jobs)[:-10]:
                if self.jobs[old]['status'] != 'running':
                    self.jobs.pop(old, None)
        Thread(target=self._technical, args=(job_id, store, site_id, runner), daemon=True).start()
        return self.job(job_id)

    def _technical(self, job_id, store, site_id, runner):
        def progress(text):
            with self.lock:
                if self.jobs[job_id]['status'] == 'running':
                    self.jobs[job_id]['phase'] = text
        try:
            site = technical.run_check(store, site_id, progress, lambda: self.job(job_id)['status'] == 'cancelled', runner)
            with self.lock:
                job = self.jobs[job_id]
                if job['status'] == 'running':
                    check = site['evidence']['appCheck']
                    job.update(status='complete', phase=site['evidence']['technical'], standard=check['standard'],
                               issues=len(check['issues']))
        except Exception as error:
            with self.lock:
                job = self.jobs[job_id]
                if job['status'] == 'running':
                    job.update(status='failed', phase='Technische Prüfung fehlgeschlagen. Nichts übernommen.', error=str(error))

    def cancel(self, job_id):
        with self.lock:
            job = self.jobs[identifier(job_id)]
            if job['status'] == 'running':
                job.update(status='cancelled', phase='Abgebrochen. Bisherige Projekte bleiben erhalten.')
            return deepcopy(job)

    def _run(self, job_id, selection, source='auto'):
        try:
            candidate = self.store('area-' + digest(selection)[:16])
            data = raw = None
            if not (candidate.directory / 'project.json').exists():
                with cancel_when(lambda: self.job(job_id)['status'] == 'cancelled'):
                    data, raw = self.prepare(selection) if source == 'auto' else self.prepare(selection, source)
            # Cancellation and the final import cannot overtake each other.
            with self.lock:
                job = self.jobs[job_id]
                if job['status'] != 'running':
                    return
                if data is not None:
                    # Inspect existing projects before importing a new area. Never
                    # change their decisions or silently merge nearby junctions.
                    existing = []
                    for path in sorted(self.root.glob('*/project.json')):
                        if path.parent.resolve() == candidate.directory:
                            continue
                        other = self.stores.setdefault(path.parent.name, ProjectStore(path.parent))
                        existing.extend((path.parent.name, s) for s in other.snapshot()['sites'])
                    duplicates = []
                    unique = []
                    for site in data['sites']:
                        owner = duplicate_of(site, existing)
                        if owner:
                            duplicates.append(dict(candidateId=site['id'], **owner))
                        else:
                            unique.append(site)
                    data = deepcopy(data)
                    data['sites'] = unique
                    data['source']['existingJunctions'] = duplicates
                    atomic_write(candidate.directory / 'osm-snapshot.json', raw)
                    candidate.import_dataset(data)
                snap = candidate.snapshot()
                job.update(status='complete', phase='Sichtprüfung vorbereitet.', projectId=candidate.directory.name,
                           count=len(snap['sites']), skippedDuplicates=len(snap['source'].get('existingJunctions', [])))
        except Exception as error:
            with self.lock:
                job = self.jobs[job_id]
                if job['status'] == 'running':
                    job.update(status='failed', phase='Vorbereitung fehlgeschlagen.', error=str(error))
        finally:
            with self.lock:
                self.working.discard(job_id)
