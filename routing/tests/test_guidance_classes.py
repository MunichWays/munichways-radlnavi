"""Verify the new classes survive real OSRM extraction and response assembly."""

import json
import urllib.request


for port in (18081, 18082):
    for coordinates in ("11,48.9;11.002,48.902", "11.002,48.902;11,48.9"):
        url = (f"http://localhost:{port}/route/v1/bike/{coordinates}"
               "?steps=true&overview=false&radiuses=5;5")
        with urllib.request.urlopen(url, timeout=10) as response:
            payload = json.load(response)
        classes = []
        for step in payload["routes"][0]["legs"][0]["steps"]:
            for intersection in step["intersections"]:
                if "out" not in intersection:
                    continue
                way_classes = set(intersection.get("classes", [])) & {"road", "cycleway"}
                assert len(way_classes) == 1, intersection
                way_type = next(iter(way_classes))
                if not classes or classes[-1] != way_type:
                    classes.append(way_type)
        assert classes == ["road", "cycleway", "road"], (port, coordinates, classes)

print("OSRM guidance classes passed for Standard and Direct, both directions")
