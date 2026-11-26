// Frozen RadlNavi boundaries, bundled so selecting Munich never needs Overpass.
export const districtName = feature => `${feature.properties.bezirk_nummer} ${feature.properties.name.replace(/^\d+\s+/, '')}`;
export const districtOutlines = feature => feature.geometry.coordinates.flatMap(polygon => polygon);
export const districtSelection = feature => ({districtId: feature.properties.bezirk_nummer, name: districtName(feature)});
let pending;
export function loadDistricts() {
  if (!pending) pending = fetch('/stadtbezirke.geojson').then(async response => {
    if (!response.ok) throw new Error('Münchner Stadtbezirke konnten nicht geladen werden. Seite neu laden.');
    const data = await response.json();
    if (data.type !== 'FeatureCollection' || data.features?.length !== 25) throw new Error('Die Münchner Bezirksdaten sind unvollständig.');
    return [...data.features].sort((a,b) => a.properties.bezirk_nummer.localeCompare(b.properties.bezirk_nummer));
  }).catch(error => { pending = null; throw error; });
  return pending;
}
let visible = false;
try { visible = localStorage.getItem('junction-review:districts') === 'on'; } catch { /* Optional. */ }
const listeners = new Set();
export function attachDistricts({container, svg, project, el, html, refresh}) {
  const layer = el('g', {'pointer-events':'none', 'aria-hidden':'true'});
  svg.append(layer);
  const label = html('label', {className:'map-district-toggle'});
  const checkbox = html('input', {type:'checkbox', checked:visible});
  const caption = html('span', {}, 'Stadtbezirke München');
  label.append(checkbox, caption); container.append(label);
  let rendered = false, disposed = false;
  async function render() {
    checkbox.checked = visible; layer.setAttribute('visibility', visible ? 'visible' : 'hidden');
    if (!visible || rendered || disposed) return;
    try {
      const features = await loadDistricts();
      if (disposed || !svg.isConnected || rendered) return;
      for (const feature of features) {
        const name = districtName(feature);
        for (const coordinates of districtOutlines(feature)) {
          const path = el('polyline', {points:coordinates.map(p => project.to(p).join(',')).join(' '),
            fill:'none',stroke:'#800080','stroke-width':3,'stroke-opacity':.95,
            'stroke-dasharray':'5 5','vector-effect':'non-scaling-stroke'});
          path.append(el('title', {}, name)); layer.append(path);
        }
        const [x,y] = project.to(feature.properties.label_coordinate);
        const marker = el('g', {'data-screen-marker':'true','data-x':x,'data-y':y});
        marker.append(el('text', {'text-anchor':'middle',fill:'#800080',stroke:'white','stroke-width':3,
          'paint-order':'stroke','font-size':12,'font-weight':600}, name));
        layer.append(marker);
      }
      rendered = true; caption.textContent = 'Stadtbezirke München'; refresh();
    } catch (error) {
      if (!disposed) { caption.textContent = 'Bezirke nicht geladen – erneut wählen'; label.title = error.message; }
    }
  }
  checkbox.addEventListener('change', () => {
    visible = checkbox.checked;
    try { localStorage.setItem('junction-review:districts',visible ? 'on':'off'); } catch { /* Optional. */ }
    for (const listener of listeners) listener();
  });
  listeners.add(render); render();
  return () => { disposed = true; listeners.delete(render); };
}
