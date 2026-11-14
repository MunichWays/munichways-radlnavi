// Point-only filter: exactly four connected primary/secondary/tertiary segments.
// Segment degree is not the number of logical arms of a divided-road junction.
// Diagnostic candidates only: all four difficult examples pass this filter.
// Never activate simplified guidance directly from this result.
[out:json][timeout:60];
way[highway~"^(primary|secondary|tertiary)(_link)?$"]({{bbox}})->.roads;
node(way_link.roads:4)({{bbox}})->.fourWay;

// Remove nodes on roundabouts/circular junctions and mini-roundabouts.
way[junction~"^(roundabout|circular)$"]({{bbox}})->.roundabouts;
(
  node(w.roundabouts);
  node[highway=mini_roundabout]({{bbox}});
)->.excluded;

(.fourWay; - .excluded;)->.candidates;
.candidates out body;

{{style:
node { color: #c62828; fill-color: #e53935; symbol-size: 9; }
}}
