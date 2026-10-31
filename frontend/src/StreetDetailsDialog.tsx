import React, { useEffect, useRef, useState } from 'react';
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, LinearProgress, useMediaQuery, useTheme } from '@mui/material';
import { StreetCandidate, StreetFeature, StreetProperties, StreetSearchResult, streetLinks, streetName, streetRating, streetText } from './streetDetails';
import { StreetDetailsClient } from './streetDetailsClient';

export type StreetQuery = { lat: number; lng: number; zoom: number };
type Props = { query: StreetQuery | null; onHighlight: (feature: StreetFeature | null) => void };

function DetailFields({ properties: p }: { properties: StreetProperties }) {
  const rating = streetRating(p);
  const row = (label: string, value: unknown) => {
    const text = streetText(value);
    return text ? <div className="street-detail-row" key={label}><dt>{label}</dt><dd>{text}</dd></div> : null;
  };
  const links = (label: string, value: unknown, hideAllWays = false) => streetLinks(value)
    .filter(link => !hideAllWays || link.title.toLowerCase() !== '-n/a-alle-wege')
    .map(link => <div className="street-detail-row" key={`${label}-${link.url}`}><dt>{label}</dt><dd>
      <a href={link.url} target="_blank" rel="noopener noreferrer">{link.title}</a>
    </dd></div>);
  const section = (title: string, items: React.ReactNode[], expanded = false) => {
    const children = React.Children.toArray(items);
    return children.length ? <details open={expanded || undefined} className="street-detail-section">
      <summary>{title}</summary><dl>{children}</dl></details> : null;
  };
  const width = streetText(p.osm_width);
  return <>
    <h3 className="street-detail-name">{streetName(p)}</h3>
    <p><span className="street-rating-dot" style={{ backgroundColor: rating.color }} />{rating.label}
      {rating.bicycleClass !== undefined && ` · OSM class:bicycle: ${rating.bicycleClass}`}</p>
    {streetText(p.osm_name) && streetText(p.munichways_name) && <dl>
      {row('OSM', p.osm_name)}{row('MunichWays', p.munichways_name)}
    </dl>}
    {section('Ist-Zustand', [
      row('Ist-Situation', p.munichways_current), row('Beschreibung', p.munichways_description),
      ...links('Strecke', p.munichways_route_link, true), row('RadlVorrangNetz', p.munichways_mw_rv_route),
      row('Neuralgischer Punkt', p.munichways_neuralgic_point), row('Straßenart', p.osm_highway),
      row('Oberfläche', p.osm_surface), row('Ebenheit', p.osm_smoothness), row('Fahrradregelung', p.osm_bicycle),
      row('Zugang', p.osm_access), row('Breite', width && /^\d+(?:[.,]\d+)?$/.test(width) ? `${width} Meter` : width),
      row('Beleuchtung', p.osm_lit),
    ], true)}
    {section('Forderungen und Netzplanung', [
      row('Soll-Maßnahmen', p.munichways_target), ...links('Maßnahmen-Kategorie', p.munichways_measure_category_link),
      row('Status-Umsetzung', p.munichways_status_implementation), row('Netztyp Planung', p.munichways_net_type_plan),
      row('Netztyp Ziel', p.munichways_net_type_target), ...links('Bezirk', p.munichways_district_link),
    ])}
    {section('Weitere Links', [...links('Weiterer Link', p.munichways_links), ...links('Mapillary', p.munichways_mapillary_link)])}
    {section('Technische Angaben', [row('MunichWays-ID', p.munichways_id), row('OSM-ID', p.osm_id),
      ...links('OpenStreetMap', /^\d+$/.test(String(p.osm_id)) ? `https://www.openstreetmap.org/way/${p.osm_id}` : undefined),
    ])}
  </>;
}

/** One owner for menu search, dialog loads and cancellation; route state is never touched. */
export default function StreetDetailsControl({ query, onHighlight }: Props) {
  const clientRef = useRef<StreetDetailsClient>();
  const [search, setSearch] = useState<StreetSearchResult | null>(null);
  const [searchError, setSearchError] = useState('');
  const [searchBusy, setSearchBusy] = useState(false);
  const [searchRetry, setSearchRetry] = useState(0);
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<StreetCandidate | null>(null);
  const [properties, setProperties] = useState<StreetProperties | null>(null);
  const [detailError, setDetailError] = useState('');
  const [detailRetry, setDetailRetry] = useState(0);
  const [detailBusy, setDetailBusy] = useState(false);
  const fullScreen = useMediaQuery(useTheme().breakpoints.down('sm'));
  if (!clientRef.current) clientRef.current = new StreetDetailsClient();
  useEffect(() => () => clientRef.current?.dispose(), []);

  useEffect(() => {
    const controller = new AbortController();
    setOpen(false); setSelected(null); setProperties(null); onHighlight(null);
    setSearch(null); setSearchError(''); setSearchBusy(false);
    if (!query || query.zoom < 14) return () => controller.abort();
    setSearchBusy(true);
    clientRef.current!.search(query.lat, query.lng, query.zoom, controller.signal)
      .then(result => { if (!controller.signal.aborted) setSearch(result); })
      .catch(error => { if (!controller.signal.aborted) setSearchError(error.message || 'Die Streckensuche ist fehlgeschlagen.'); })
      .finally(() => { if (!controller.signal.aborted) setSearchBusy(false); });
    return () => controller.abort();
  }, [query, searchRetry, onHighlight]);

  useEffect(() => {
    const controller = new AbortController();
    setProperties(null); setDetailError(''); setDetailBusy(false);
    onHighlight(open ? selected : null);
    if (open && search && selected) {
      setDetailBusy(true);
      clientRef.current!.details(search.manifest, selected.id, controller.signal)
        .then(p => { if (!controller.signal.aborted) setProperties(p); })
        .catch(error => { if (!controller.signal.aborted) setDetailError(error.message || 'Die Streckendetails konnten nicht geladen werden.'); })
        .finally(() => { if (!controller.signal.aborted) setDetailBusy(false); });
    }
    return () => controller.abort();
  }, [open, search, selected, detailRetry, onHighlight]);

  const close = () => { setOpen(false); onHighlight(null); };
  const showDetails = () => {
    setSelected(search?.candidates.length === 1 ? search.candidates[0] : null);
    setOpen(true);
  };
  return <>
    {query && <div className="street-menu-status" aria-live="polite">
      {query.zoom < 14 ? <p>Für Streckendetails bitte hineinzoomen.</p> : searchBusy ? <p role="status">Streckendetails werden gesucht …</p> :
        searchError ? <><p role="alert">{searchError}</p><Button onClick={() => setSearchRetry(v => v + 1)}>Streckensuche wiederholen</Button></> :
          search && search.candidates.length ? <Button onClick={showDetails}>Details anzeigen</Button> :
            search ? <p>Für diese Stelle sind keine V20-Streckendetails vorhanden.</p> : null}
    </div>}
    <Dialog open={open} onClose={close} fullWidth maxWidth="sm" fullScreen={fullScreen}
      aria-labelledby="street-details-title" PaperProps={{ className: 'street-details-dialog', sx: fullScreen ? {
        position: 'fixed', inset: 0, width: '100vw', maxWidth: '100vw',
        height: '100dvh', maxHeight: '100dvh', boxSizing: 'border-box', overflow: 'hidden',
      } : undefined }}>
      <DialogTitle id="street-details-title">V20-Streckendetails</DialogTitle>
      <DialogContent dividers>
        {search && <p className="street-snapshot">Daten abgerufen am {new Date(search.manifest.retrievedAt).toLocaleDateString('de-DE')} · V20</p>}
        {search && search.candidates.length > 1 && <>
          <p>Mehrere Strecken an dieser Stelle. Bitte einen Abschnitt auswählen:</p>
          <div className="street-candidates" role="group" aria-label="Streckenabschnitt auswählen">
            {search.candidates.map(candidate => <Button key={candidate.id} variant={selected?.id === candidate.id ? 'contained' : 'outlined'}
              aria-pressed={selected?.id === candidate.id} onClick={() => setSelected(candidate)}>
              {streetName(candidate.properties)} · {streetRating(candidate.properties).label} · OSM {candidate.id.slice(4)}
            </Button>)}
          </div>
        </>}
        {detailBusy && <div role="status"><p>Streckendetails werden geladen …</p><LinearProgress /></div>}
        {detailError && <Alert severity="error" action={<Button color="inherit" onClick={() => setDetailRetry(v => v + 1)}>Erneut versuchen</Button>}>{detailError}</Alert>}
        {properties && <DetailFields properties={properties} />}
      </DialogContent>
      <DialogActions><Button onClick={close}>Schließen</Button></DialogActions>
    </Dialog>
  </>;
}
