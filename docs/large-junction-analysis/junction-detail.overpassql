// First detail view: zoom to 48.10845, 11.6040 (Balanstrasse / Chiemgaustrasse).
// Move/zoom the map to another candidate and rerun for its detail view.
[out:json][timeout:60];
(
  way[highway]({{bbox}});
  node[highway=traffic_signals]({{bbox}});
  node[highway=crossing]({{bbox}});
  nwr[junction=yes]({{bbox}});
);
out body geom;

{{style:
way { color: #808080; width: 3; }
way[highway=path], way[highway=cycleway], way[highway=footway] {
  color: #1565c0; width: 4;
}
way[footway=crossing], way[cycleway=crossing] {
  color: #00acc1; width: 6;
}
node { color: #777777; symbol-size: 3; }
node[highway=traffic_signals] { color: #c62828; fill-color: #e53935; symbol-size: 9; }
node[highway=crossing] { color: #ef6c00; fill-color: #ff9800; symbol-size: 7; }
way[junction=yes] { color: #8e24aa; fill-color: #ce93d8; fill-opacity: 0.3; }
}}
