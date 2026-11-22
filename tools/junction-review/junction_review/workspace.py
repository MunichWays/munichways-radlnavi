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

    def start(self, selection):
        selection_query(selection)  # Reject invalid geometry before creating a job.
        selection = deepcopy(selection)
        with self.lock:
            if self.working:
                raise Conflict('Eine OSM-Vorbereitung läuft noch. Nach einem Abbruch muss der laufende Abruf erst auslaufen; bitte kurz warten.')
            job_id = uuid.uuid4().hex
            self.jobs[job_id] = dict(id=job_id, status='running', phase='OSM-Daten laden und Kreuzungen vorbereiten …')
            self.working.add(job_id)
            # Terminal jobs need not accumulate for the lifetime of the server.
            for old in list(self.jobs)[:-10]:
                if old not in self.working:
                    self.jobs.pop(old, None)
        Thread(target=self._run, args=(job_id, selection), daemon=True).start()
        return self.job(job_id)

    def job(self, job_id):
        with self.lock:
            return deepcopy(self.jobs[identifier(job_id)])

    def current(self):
        with self.lock:
            return next((deepcopy(j) for j in self.jobs.values() if j['status'] == 'running'), None)

    def cancel(self, job_id):
        with self.lock:
            job = self.jobs[identifier(job_id)]
            if job['status'] == 'running':
                job.update(status='cancelled', phase='Abgebrochen. Bisherige Projekte bleiben erhalten.')
            return deepcopy(job)

    def _run(self, job_id, selection):
        try:
            candidate = self.store('area-' + digest(selection)[:16])
            data = raw = None
            if not (candidate.directory / 'project.json').exists():
                with cancel_when(lambda: self.job(job_id)['status'] == 'cancelled'):
                    data, raw = self.prepare(selection)
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
