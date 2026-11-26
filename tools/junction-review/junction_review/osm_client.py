"""Bounded Overpass transport, retryable errors and a shared short-lived cache."""
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from http.client import HTTPException
import json
import re
from threading import Lock
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

ENDPOINT = 'https://overpass-api.de/api/interpreter'
ENDPOINTS = (ENDPOINT, 'https://overpass.private.coffee/api/interpreter')
_cancelled = ContextVar('osm_cancelled', default=lambda: False)


@contextmanager
def cancel_when(predicate):
    token = _cancelled.set(predicate)
    try:
        yield
    finally:
        _cancelled.reset(token)


class OsmUnavailable(ValueError):
    """Temporary upstream failure; distinct from invalid local geometry."""


class OverpassClient:
    def __init__(self, opener=urlopen, sleep=time.sleep, clock=time.monotonic, endpoints=ENDPOINTS):
        self.opener, self.sleep, self.clock = opener, sleep, clock
        self.endpoints = tuple(endpoints)
        if not self.endpoints:
            raise ValueError('Mindestens ein OSM-Dienst ist erforderlich.')
        self.endpoint_index = 0
        self.lock = Lock()
        self.cache = OrderedDict()

    def query(self, query):
        # One local user, one upstream call at a time. Identical requests after
        # double submission/cancellation share the successful cached response.
        with self.lock:
            if _cancelled.get()():
                raise OsmUnavailable('Abgebrochen.')
            cached = self.cache.get(query)
            if cached and self.clock() - cached[0] < 900:
                self.cache.move_to_end(query)
                return deepcopy(cached[1])
            match = re.search(r'\[timeout:(\d+)\]', query)
            timeout = min(165, int(match[1]) + 10) if match else 40
            failures = []
            for attempt in range(3):
                if _cancelled.get()():
                    raise OsmUnavailable('Abgebrochen.')
                delay = 2 * (attempt + 1)
                endpoint = self.endpoints[self.endpoint_index]
                request = Request(endpoint, data=urlencode({'data': query}).encode(),
                                  headers={'User-Agent': 'JunctionReview/1.0 (local human geometry review)'})
                try:
                    with self.opener(request, timeout=timeout) as response:
                        raw = response.read(40_000_001)
                    if len(raw) > 40_000_000:
                        raise ValueError('Zu viele OSM-Daten. Bitte ein kleineres Gebiet auswählen.')
                    try:
                        data = json.loads(raw)
                    except (ValueError, UnicodeError) as error:
                        raise OsmUnavailable('Der OSM-Dienst lieferte keine gültige Antwort. Bitte erneut versuchen.') from error
                    if not isinstance(data, dict) or not isinstance(data.get('elements'), list):
                        raise OsmUnavailable('Die Antwort des OSM-Dienstes ist unvollständig. Bitte erneut versuchen.')
                    if data.get('remark'):
                        if 'out of memory' in data['remark'].lower():
                            raise ValueError('Das Gebiet ist für den OSM-Dienst zu groß. Bitte eine kleinere Fläche wählen.')
                        raise OsmUnavailable('Die OSM-Abfrage wurde vorzeitig beendet. Bitte erneut versuchen oder ein kleineres Gebiet wählen.')
                    # Cache small lookups, never full city snapshots in RAM.
                    if len(raw) <= 2_000_000:
                        self.cache[query] = (self.clock(), deepcopy(data))
                        while len(self.cache) > 20:
                            self.cache.popitem(last=False)
                    return data
                except HTTPError as error:
                    code = error.code
                    error.close()
                    if code not in (408, 429, 500, 502, 503, 504):
                        raise ValueError(f'Der OSM-Dienst hat die Abfrage abgelehnt (HTTP {code}).') from error
                    failure = f'Der OSM-Dienst ist vorübergehend nicht verfügbar (HTTP {code}).'
                    retry_after = error.headers.get('Retry-After', '') if error.headers else ''
                    delay = max(15 if code == 429 else 2, min(30, int(retry_after))) if retry_after.isdigit() else (15 if code == 429 else 2)
                except OsmUnavailable as error:
                    failure = str(error)
                except (URLError, TimeoutError, ConnectionError, OSError, HTTPException) as error:
                    failure = 'Der OSM-Dienst antwortet nicht oder die Verbindung wurde unterbrochen.'
                failures.append(f'{urlsplit(endpoint).hostname}: {failure}')
                if attempt == 2:
                    raise OsmUnavailable(' '.join(dict.fromkeys(failures)) + ' Bitte kurz warten und erneut versuchen.')
                if _cancelled.get()():
                    raise OsmUnavailable('Abgebrochen.')
                # Keep the same query and total three-attempt budget. Only a
                # fully validated response may enter the cache or be imported.
                # Remember the working server for subsequent uncached requests.
                self.endpoint_index = (self.endpoint_index + 1) % len(self.endpoints)
                self.sleep(delay)


client = OverpassClient()


def query_osm(query):
    return client.query(query)
