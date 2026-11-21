"""Loopback-only application server, standard library, no external services."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from urllib.parse import unquote, urlsplit

from .adapters import export_review
from .store import Conflict

STATIC = Path(__file__).with_name('web')


def create_server(store, port=8765):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
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
            self.wfile.write(body)

        def same_origin(self):
            expected = f'127.0.0.1:{self.server.server_port}'
            return self.headers.get('Host') == expected and self.headers.get('Origin', f'http://{expected}') == f'http://{expected}'

        def do_GET(self):
            if not self.same_origin():
                self.send(403, dict(error='Nur über die lokale Projektadresse öffnen.'))
                return
            path = urlsplit(self.path).path
            try:
                if path == '/api/project':
                    self.send(200, dict(**store.snapshot(), token=token))
                elif path == '/api/export':
                    self.send(200, export_review(store.snapshot()), attachment=True)
                elif path in ('/', '/app.js', '/style.css'):
                    file = STATIC / {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}[path]
                    types = {'.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css'}
                    self.send(200, file.read_bytes(), types[file.suffix] + '; charset=utf-8')
                else:
                    self.send(404, dict(error='Nicht gefunden.'))
            except (ValueError, OSError) as error:
                self.send(400, dict(error=str(error)))

        def do_POST(self):
            if not self.same_origin() or self.headers.get('X-Review-Token') != token:
                self.send(403, dict(error='Ungültige lokale Sitzung. Ansicht neu laden.'))
                return
            try:
                path = urlsplit(self.path).path.split('/')
                if len(path) != 5 or path[1:3] != ['api', 'sites'] or path[4] not in ('save', 'preview'):
                    self.send(404, dict(error='Nicht gefunden.'))
                    return
                size = int(self.headers.get('Content-Length', 0))
                if not 0 < size <= 1000000 or self.headers.get_content_type() != 'application/json':
                    raise ValueError('JSON-Anfrage fehlt oder ist zu groß.')
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError('Ungültige Anfrage.')
                self.send(200, store.save(unquote(path[3]), payload, preview=path[4] == 'preview'))
            except Conflict as error:
                self.send(409, dict(error=str(error)))
            except KeyError:
                self.send(404, dict(error='Kreuzung nicht gefunden oder Pflichtfeld fehlt.'))
            except (ValueError, TypeError, AttributeError) as error:
                self.send(400, dict(error=str(error)))

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    return server
