"""Bundled Munich district boundaries shared with RadlNavi; no network lookup."""
from functools import lru_cache
import json
from pathlib import Path


@lru_cache(maxsize=1)
def _districts():
    path = Path(__file__).with_name('web') / 'stadtbezirke.geojson'
    return {feature['properties']['bezirk_nummer']: feature
            for feature in json.loads(path.read_text(encoding='utf-8'))['features']}


def district_feature(district_id):
    if not isinstance(district_id, str) or district_id not in _districts():
        raise ValueError('Unbekannter Münchner Stadtbezirk. Bitte BA01 bis BA25 auswählen.')
    return _districts()[district_id]
