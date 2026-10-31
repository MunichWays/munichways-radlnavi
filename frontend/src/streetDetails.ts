export type StreetProperties = Record<string, string | number | null | undefined>;
export type StreetNetworkMode = 'all' | 'priority';
export type StreetCoordinate = [number, number];
export type StreetFeature = {
  type: 'Feature'; id: string; properties: StreetProperties;
  geometry: { type: 'LineString'; coordinates: StreetCoordinate[] };
};
export type StreetManifest = {
  schemaVersion: 1; snapshot: string; sourceUrl: string; sourceCreatedAt: string; retrievedAt: string;
  bbox: [number, number, number, number]; featureCount: number;
};
export type StreetCandidate = StreetFeature & { distance: number };
export type StreetSearchResult = { manifest: StreetManifest; candidates: StreetCandidate[] };

export function streetText(value: unknown): string | undefined {
  if (typeof value !== 'string' && typeof value !== 'number') return undefined;
  const text = String(value).trim();
  return text && text !== '-' ? text : undefined;
}

export function streetName(p: StreetProperties): string {
  return streetText(p.osm_name) || streetText(p.munichways_name) || 'Streckenabschnitt';
}

export function streetSmoothness(value: unknown): string | undefined {
  const text = streetText(value);
  const labels: Record<string, string> = { excellent: 'sehr gut', good: 'gut', intermediate: 'mittelmäßig', medium: 'mittelmäßig',
    bad: 'schlecht', very_bad: 'sehr schlecht', horrible: 'sehr holprig', very_horrible: 'extrem holprig', impassable: 'unpassierbar' };
  return text ? labels[text] || text : undefined;
}

const osmLabels: Record<string, Record<string, string>> = {
  osm_highway: {
    residential: 'Wohnstraße', path: 'Weg', footway: 'Fußweg', cycleway: 'Radweg',
    primary: 'Hauptverkehrsstraße', secondary: 'Übergeordnete Straße', tertiary: 'Verbindungsstraße',
    unclassified: 'Nebenstraße', track: 'Wirtschaftsweg', service: 'Zufahrts- oder Erschließungsweg',
    living_street: 'Verkehrsberuhigter Bereich', pedestrian: 'Fußgängerzone', construction: 'Im Bau',
    steps: 'Treppe', bus_stop: 'Bushaltestelle', proposed: 'Geplant', elevator: 'Aufzug',
    road: 'Straße ohne nähere Einordnung', platform: 'Bahnsteig / Haltestellenplattform',
    motorway: 'Autobahn', trunk: 'Schnellstraße', motorway_link: 'Autobahnauffahrt oder -abfahrt',
    trunk_link: 'Schnellstraßenauffahrt oder -abfahrt', primary_link: 'Zubringer zur Hauptverkehrsstraße',
    secondary_link: 'Zubringer zur übergeordneten Straße', tertiary_link: 'Zubringer zur Verbindungsstraße',
  },
  // Meanings follow https://wiki.openstreetmap.org/wiki/DE:Key:surface.
  osm_surface: {
    asphalt: 'Asphalt', paving_stones: 'Pflastersteine', compacted: 'Verdichteter Belag', sett: 'Natursteinpflaster',
    fine_gravel: 'Feiner Schotter', gravel: 'Schotter', pebblestone: 'Kieselsteine', concrete: 'Beton',
    dirt: 'Erde', paved: 'Befestigt', ground: 'Naturboden', wood: 'Holz', grass: 'Gras', unpaved: 'Unbefestigt',
    chipseal: 'Bitumen mit eingestreutem Splitt', grass_paver: 'Rasengittersteine', 'concrete:plates': 'Betonplatten',
    metal: 'Metall', sand: 'Sand', cobblestone: 'Kopfsteinpflaster', unhewn_cobblestone: 'Unbehauenes Kopfsteinpflaster',
    metal_grid: 'Metallgitter', earth: 'Erde', 'concrete:lanes': 'Betonspurbahnen', rock: 'Fels',
    'cobblestone:flattened': 'Abgeflachtes Kopfsteinpflaster', mud: 'Schlamm', woodchips: 'Holzhackschnitzel',
  },
  osm_bicycle: {
    yes: 'Erlaubt', no: 'Nicht erlaubt', designated: 'Für Radverkehr vorgesehen',
    official: 'Offiziell für Radverkehr ausgewiesen', use_sidepath: 'Begleitenden Radweg benutzen',
    permissive: 'Vom Eigentümer geduldet', dismount: 'Absteigen und schieben', destination: 'Nur Anliegerverkehr',
    private: 'Privat', discouraged: 'Nicht empfohlen', unknown: 'Unbekannt',
  },
  osm_access: {
    yes: 'Erlaubt', no: 'Nicht erlaubt', permissive: 'Vom Eigentümer geduldet', private: 'Privat',
    destination: 'Nur Anliegerverkehr', agricultural: 'Landwirtschaftlicher Verkehr', forestry: 'Forstwirtschaftlicher Verkehr',
    designated: 'Für vorgesehenen Verkehr ausgewiesen', restricted: 'Eingeschränkt', unknown: 'Unbekannt',
    residents: 'Nur Anwohner', customers: 'Nur Kunden', delivery: 'Nur Lieferverkehr',
  },
  osm_lit: { yes: 'Ja', no: 'Nein', '24/7': 'Durchgehend', automatic: 'Automatisch', '1': 'Ja',
    limited: 'Zeitweise', sunset_sunrise: 'Von Sonnenuntergang bis Sonnenaufgang' },
};

/** Translate OSM values, including multi-values, without translating names or losing unknown tags. */
export function streetOsmText(field: string, value: unknown): string | undefined {
  const text = streetText(value);
  if (!text) return undefined;
  if (field === 'osm_smoothness') return streetSmoothness(text);
  const labels = osmLabels[field];
  if (!labels) return text === 'unknown' ? 'Unbekannt' : text;
  return text.split(/([;,])/).map(part => {
    if (/^[;,]$/.test(part)) return `${part} `;
    const trimmed = part.trim();
    const side = /^(links|rechts):\s*(.+)$/.exec(trimmed);
    return side ? `${side[1]}: ${labels[side[2]] || side[2]}` : labels[trimmed] || trimmed;
  }).join('');
}

export function streetWidth(value: unknown): string | undefined {
  const text = streetText(value);
  if (!text) return undefined;
  return text.replace(/^(?:(links|rechts):\s*)?(\d+(?:[.,]\d+)?)(?:\s*m)?$/, (_, side, width: string) =>
    `${side ? `${side}: ` : ''}${width.replace('.', ',')} Meter`);
}

const classes: Record<string, { label: string; color: string }> = {
  '3': { label: 'Hervorragend', color: '#27F5A5' },
  '2': { label: 'Gemütlich', color: '#27F5A5' },
  '1': { label: 'Durchschnittlich', color: '#FFD000' },
  '0': { label: 'Keine Aussage', color: '#9C9D9F' },
  '-1': { label: 'Stressig', color: '#F44336' },
  '-2': { label: 'Sehr stressig', color: '#000000' },
  '-3': { label: 'Unter allen Umständen vermeiden', color: '#000000' },
};
const colors: Record<string, { label: string; color: string }> = {
  green: { label: 'Grün', color: '#27F5A5' }, yellow: { label: 'Gelb', color: '#FFD000' },
  red: { label: 'Rot', color: '#F44336' }, black: { label: 'Schwarz', color: '#000000' },
  blue: { label: 'Blau', color: '#00BCF2' }, grey: { label: 'Grau', color: '#9C9D9F' },
};
export function streetRating(p: StreetProperties) {
  const bicycleClass = streetText(p.osm_class_bicycle);
  const known = bicycleClass !== undefined ? classes[bicycleClass] : undefined;
  const fallback = colors[streetText(p.color)?.toLowerCase() || ''];
  return { label: known?.label || fallback?.label || 'Nicht bewertet',
    color: known?.color || fallback?.color || '#9C9D9F', bicycleClass };
}

export function safeStreetUrl(value: unknown): string | undefined {
  const text = streetText(value);
  if (!text || !/^https?:\/\//i.test(text)) return undefined;
  try {
    const url = new URL(text);
    if (url.username || url.password) return undefined;
    return url.href;
  } catch { return undefined; }
}

export function streetLinks(value: unknown): { title: string; url: string }[] {
  const text = streetText(value);
  if (!text) return [];
  // The detached document is never inserted into the live DOM.
  const doc = new DOMParser().parseFromString(text, 'text/html');
  const anchors = Array.from(doc.querySelectorAll('a'));
  const links = anchors.length ? anchors.map(a => ({ title: streetText(a.textContent), url: a.getAttribute('href') }))
    : text.split(',').map(part => ({ title: undefined, url: part.trim() }));
  const seen = new Set<string>();
  return links.flatMap(link => {
    const url = safeStreetUrl(link.url);
    if (!url || seen.has(url)) return [];
    seen.add(url);
    return [{ title: link.title || url, url }];
  });
}

export function streetDetailGroup(id: string): string {
  if (!/^osm_\d+$/.test(id)) throw new Error('Ungültige Strecken-ID.');
  return id.slice(4).slice(-2).padStart(2, '0');
}

export function mapillaryPreview(p: StreetProperties): { id: string; url: string; embedUrl: string } | undefined {
  const links = streetLinks(p.munichways_mapillary_link);
  for (const link of links) {
    const url = new URL(link.url);
    if (!['www.mapillary.com', 'mapillary.com'].includes(url.hostname) || url.protocol !== 'https:') continue;
    const id = url.searchParams.get('pKey') || url.searchParams.get('image_key');
    if (!id || !/^[A-Za-z0-9_-]+$/.test(id)) continue;
    return { id, url: `https://www.mapillary.com/app/?pKey=${encodeURIComponent(id)}`,
      embedUrl: `https://www.mapillary.com/embed?image_key=${encodeURIComponent(id)}&style=photo` };
  }
  return undefined;
}

export function streetSourceLabel(manifest: StreetManifest): string {
  const [year, month, day] = manifest.sourceCreatedAt.split('-');
  const filename = new URL(manifest.sourceUrl).pathname.split('/').pop();
  return `Datenstand ${day}.${month}.${year}, Quelle ${filename}.`;
}

export function streetSearchRadius(lat: number, zoom: number): number {
  // Web Mercator scale is rotation independent and uses CSS pixels.
  return Math.min(20, 8 * 156543.03392804097 * Math.cos(lat * Math.PI / 180) / 2 ** zoom);
}
