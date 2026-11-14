// Overpass Turbo: intersections within primary/secondary/tertiary, including links.
// Includes tertiary/tertiary intersections; no primary/secondary prerequisite.
[out:json][timeout:60];
way[highway~"^(primary|secondary|tertiary)(_link)?$"]({{bbox}})->.roads;
node(way_link.roads:3-)({{bbox}})->.candidates;
.candidates out body;
way(bn.candidates)[highway~"^(primary|secondary|tertiary)(_link)?$"];
out geom;

{{style:
way { color: #777777; width: 3; opacity: 0.6; }
node { color: #c62828; fill-color: #e53935; symbol-size: 9; }
}}
