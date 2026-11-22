[out:json][timeout:120];
area[boundary=administrative][admin_level=6][name="München"]->.city;
way[highway=primary](area.city)->.roads;
node(way_link.roads:3-)(area.city)->.junctions;
.junctions out body;
way(bn.junctions)[highway=primary];
out body geom;
