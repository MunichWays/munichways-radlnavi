[out:json][timeout:120];
rel(62428); out tags;
area(3600062428)->.munich;
way(area.munich)[highway][~"^(cycleway:((left|right|both):(surface|smoothness|width)|(surface|smoothness|width):(left|right|both))|(surface|smoothness|width):(left|right|both))$"~"."];
out body center;
