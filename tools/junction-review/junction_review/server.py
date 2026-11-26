"""Loopback HTTP adapter. Project state and background work live in Workspace."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from urllib.parse import parse_qs, unquote, urlsplit

from .adapters import export_review
from .discovery import discover, search_areas, areas_at, area_boundary, selection_query
from .osm_client import OsmUnavailable
from .render import review_svg
from .store import Conflict
from .workspace import Workspace

STATIC = Path(__file__).with_name('web')


def create_server(store, port=8765):
    token = secrets.token_urlsafe(32)
    workspace = Workspace(store, prepare=lambda selection: discover(selection))

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, format, *args):
            pass

        def send(self, status, body, content_type='application/json; charset=utf-8', attachment=False):
            if content_type.startswith('application/json'):
                body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
            elif isinstance(body, str):
                body = body.encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: https://tile.openstreetmap.org; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
            self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
            if attachment:
                self.send_header('Content-Disposition', 'attachment; filename="junction-review-export.json"')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def same_origin(self):
            expected = f'127.0.0.1:{self.server.server_port}'
            return self.headers.get('Host') == expected and self.headers.get('Origin', f'http://{expected}') == f'http://{expected}'

        def project_store(self):
            query = parse_qs(urlsplit(self.path).query)
            project_id = self.headers.get('X-Review-Project') or query.get('project', [None])[0]
            return workspace.store(project_id)

        def snapshot(self, target):
            return dict(**workspace.snapshot(target), token=token)

        def do_GET(self):
            if not self.same_origin():
                self.send(403, dict(error='Nur über die lokale Projektadresse öffnen.'))
                return
            path = urlsplit(self.path).path
            try:
                if path in ('/', '/app.js', '/drawing.js', '/api.js', '/area-ui.js', '/gate-ui.js', '/districts.js', '/stadtbezirke.geojson', '/style.css'):
                    file = STATIC / ('index.html' if path == '/' else path[1:])
                    types = {'.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.geojson': 'application/geo+json'}
                    self.send(200, file.read_bytes(), types[file.suffix] + '; charset=utf-8')
                elif path == '/api/project':
                    self.send(200, self.snapshot(self.project_store()))
                elif path == '/api/projects':
                    self.send(200, workspace.projects(self.project_store()))
                elif path == '/api/export':
                    self.send(200, export_review(self.project_store().snapshot()), attachment=True)
                elif path == '/api/jobs/current':
                    self.send(200, workspace.current())
                elif path.startswith('/api/jobs/') and len(path.split('/')) == 4:
                    self.send(200, workspace.job(path.split('/')[3]))
                elif path.startswith('/api/sites/') and path.endswith('/image.svg') and len(path.split('/')) == 5:
                    site_id = unquote(path.split('/')[3])
                    site = next((s for s in self.project_store().snapshot()['sites'] if s['id'] == site_id), None)
                    if site is None:
                        raise KeyError(site_id)
                    self.send(200, review_svg(site), 'image/svg+xml; charset=utf-8')
                else:
                    self.send(404, dict(error='Nicht gefunden.'))
            except KeyError:
                self.send(404, dict(error='Projekt, Auftrag oder Kreuzung nicht gefunden.'))
            except (ValueError, OSError) as error:
                self.send(400, dict(error=str(error)))

        def do_POST(self):
            if not self.same_origin() or self.headers.get('X-Review-Token') != token:
                # Unread POST bytes can replace the 403 with a TCP reset on Windows.
                try:
                    size = int(self.headers.get('Content-Length', 0))
                    if 0 < size <= 1000000:
                        self.rfile.read(size)
                except (ValueError, OSError):
                    pass
                self.send(403, dict(error='Ungültige lokale Sitzung. Ansicht neu laden.'))
                return
            try:
                size = int(self.headers.get('Content-Length', 0))
                if not 0 < size <= 1000000 or self.headers.get_content_type() != 'application/json':
                    raise ValueError('JSON-Anfrage fehlt oder ist zu groß.')
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError('Ungültige Anfrage.')
                path = urlsplit(self.path).path
                parts = path.split('/')
                if path == '/api/areas/search':
                    self.send(200, search_areas(payload.get('name', '')))
                elif path == '/api/areas/at':
                    self.send(200, areas_at(payload['location']))
                elif path == '/api/areas/boundary':
                    self.send(200, area_boundary(payload['id']))
                elif path == '/api/areas/validate':
                    selection_query(dict(area=payload['area']))
                    self.send(200, dict(valid=True))
                elif path == '/api/projects/select':
                    self.send(200, self.snapshot(workspace.store(payload['id'])))
                elif path == '/api/projects/rename':
                    target = workspace.store(payload['id'])
                    target.rename(payload['name'], payload['expectedName'])
                    self.send(200, self.snapshot(target))
                elif path == '/api/areas/prepare':
                    self.send(202, workspace.start(payload['selection']))
                elif len(parts) == 5 and parts[1:3] == ['api', 'jobs'] and parts[4] == 'cancel':
                    self.send(200, workspace.cancel(parts[3]))
                elif len(parts) == 5 and parts[1:3] == ['api', 'sites'] and parts[4] in ('save', 'preview'):
                    self.send(200, self.project_store().save(unquote(parts[3]), payload, preview=parts[4] == 'preview'))
                else:
                    self.send(404, dict(error='Nicht gefunden.'))
            except OsmUnavailable as error:
                self.send(503, dict(error=str(error), retryable=True))
            except Conflict as error:
                self.send(409, dict(error=str(error)))
            except KeyError:
                self.send(404, dict(error='Projekt, Auftrag oder Kreuzung nicht gefunden oder Pflichtfeld fehlt.'))
            except (ValueError, TypeError, AttributeError, OSError) as error:
                self.send(400, dict(error=str(error)))

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    return server
