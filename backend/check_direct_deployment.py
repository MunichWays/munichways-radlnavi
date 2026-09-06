"""Check the direct API contract before advertising its public URL."""

import argparse
import json
from urllib.request import Request, urlopen


def check(fetch):
    capabilities = fetch("/routing_variants")
    if capabilities.get("default") != "direct":
        raise ValueError("Expected a direct API, not the standard service")
    payload = fetch(
        "/route/v1/bike/11.540013,48.156304;11.568796,48.102548;11.655645,48.120477"
        "?variant=direct&steps=true&annotations=nodes,distance&geometries=geojson&overview=full"
    )
    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise ValueError("Direct routing did not return a route")
    route = payload["routes"][0]
    if route.get("weight_name") != "distance" or len(route.get("legs", [])) != 2:
        raise ValueError(
            "Direct route must use distance weighting and preserve both legs"
        )
    if route.get("geometry", {}).get("type") != "LineString":
        raise ValueError("Direct route is missing GeoJSON geometry")
    legs = []
    for i, leg in enumerate(route["legs"]):
        if not leg.get("steps") or leg["steps"][-1]["maneuver"]["type"] != "arrive":
            raise ValueError("Direct route is missing navigation steps")
        annotation = leg["annotation"]
        legs.append(
            dict(
                nodes=annotation["nodes"],
                distance=annotation["distance"],
                start=payload["waypoints"][i]["location"],
                end=payload["waypoints"][i + 1]["location"],
            )
        )
    analysis = fetch("/tag_distribution", {"variant": "direct", "legs": legs})
    comfort = analysis.get("comfort")
    if analysis.get("ok") is not True or not isinstance(comfort, dict):
        raise ValueError("Direct comfort analysis is unavailable")
    if not isinstance(comfort.get("sufficientCoverage"), bool):
        raise ValueError("Direct comfort response has an invalid contract")
    # Low coverage and index=null are valid; do not require a particular map rating.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()

    def fetch(path, body=None):
        request = Request(
            args.base_url.rstrip("/") + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=45) as response:
            return json.load(response)

    check(fetch)
    print(
        "Direct API: distance profile, navigation, intermediate stop and comfort analysis OK"
    )


if __name__ == "__main__":
    main()
