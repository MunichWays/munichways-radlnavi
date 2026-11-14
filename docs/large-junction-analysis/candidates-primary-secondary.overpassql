// Overpass Turbo: candidates in the visible map extent, not junction polygons.
[out:json][timeout:60];
way[highway~"^(primary|secondary)(_link)?$"]({{bbox}})->.roads;
// Count connected road segments, not OSM ways (which may be arbitrarily split).
node(way_link.roads:3-)({{bbox}})->.candidates;
.candidates out body;
way(bn.candidates)[highway~"^(primary|secondary)(_link)?$"];
out geom;

{{style:
way { color: #777777; width: 3; opacity: 0.6; }
node { color: #c62828; fill-color: #e53935; symbol-size: 9; }
}}
