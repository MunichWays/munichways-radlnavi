"""Check public capabilities without granting the GitHub runner Cloud Run IAM."""

import argparse
import json
from urllib.request import urlopen


def direct_enabled(base_url, fetch=urlopen):
    with fetch(base_url.rstrip("/") + "/routing_variants", timeout=30) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or payload.get("default") != "standard":
        raise ValueError("Expected capabilities from the Standard API")
    direct = payload.get("direct")
    if not isinstance(direct, dict) or type(direct.get("available")) is not bool:
        raise ValueError("Expected a boolean direct.available capability")
    return direct["available"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    print("true" if direct_enabled(args.base_url) else "false")
