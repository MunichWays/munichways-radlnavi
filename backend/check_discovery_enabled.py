"""Check public capabilities without granting the GitHub runner Cloud Run IAM."""

import argparse
import json
from urllib.request import urlopen


def discovery_enabled(base_url, fetch=urlopen):
    with fetch(base_url.rstrip("/") + "/routing_variants", timeout=30) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or payload.get("default") != "standard":
        raise ValueError("Expected capabilities from the Standard API")
    discovery = payload.get("discovery")
    if not isinstance(discovery, dict) or type(discovery.get("available")) is not bool:
        raise ValueError("Expected a boolean discovery.available capability")
    return discovery["available"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    print("true" if discovery_enabled(args.base_url) else "false")
