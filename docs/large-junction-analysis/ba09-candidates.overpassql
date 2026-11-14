[out:json][timeout:120];
relation[boundary=administrative][name="Neuhausen-Nymphenburg"]->.boundary;
.boundary map_to_area ->.district;
way[highway~"^(primary|secondary|tertiary)(_link)?$"](area.district)->.roads;
node(way_link.roads:4)(area.district)->.candidates;
.boundary out tags geom;
.roads out body geom;
.candidates out body;
