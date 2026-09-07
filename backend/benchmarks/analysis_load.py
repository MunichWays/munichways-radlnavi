"""ABBA load comparison of two explicitly authorized LOCAL analysis workers.

Each worker must have separate CPU/memory limits. The same frozen annotated route
is used for both variants to compare the identical analysis workload. This does
not benchmark OSRM, production cold starts or the device/network path.
"""

import argparse
import asyncio
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter

import httpx


def summary(samples):
    values = sorted(samples)
    return {
        "count": len(values),
        "p50_ms": round(values[len(values) // 2], 2),
        "p95_ms": round(values[math.ceil(len(values) * 0.95) - 1], 2),
        "max_ms": round(values[-1], 2),
    }


async def run(args):
    fixture = json.loads(args.fixture.read_text())
    legs = [
        dict(
            nodes=leg["annotation"]["nodes"],
            distance=leg["annotation"]["distance"],
            start=fixture["waypoints"][i],
            end=fixture["waypoints"][i + 1],
        )
        for i, leg in enumerate(fixture["legs"])
    ]
    hashes = {}
    async with httpx.AsyncClient(timeout=60, trust_env=False) as client:

        async def request(variant, scheduled):
            await asyncio.sleep(max(0, scheduled - perf_counter()))
            endpoint = getattr(args, variant)
            response = await client.post(
                endpoint + "/tag_distribution", json=dict(variant=variant, legs=legs)
            )
            response.raise_for_status()
            payload = response.json()
            assert payload["ok"] and payload["analysis"]["distanceComplete"], payload
            digest = hashlib.sha256(
                json.dumps(payload, sort_keys=True).encode()
            ).hexdigest()
            assert (
                hashes.setdefault(variant, digest) == digest
            ), "Analysis output changed"
            return (perf_counter() - scheduled) * 1000

        for variant in ("standard", "direct"):
            for _ in range(3):
                await request(variant, perf_counter())
        assert (
            hashes["standard"] == hashes["direct"]
        ), "Variant changed identical analysis input"
        for mixed in (False, True, True, False):
            start = perf_counter() + 0.1
            standard = [
                asyncio.create_task(request("standard", start + i / args.rate))
                for i in range(args.samples)
            ]
            direct = (
                [
                    asyncio.create_task(request("direct", start + i / args.rate))
                    for i in range(args.samples)
                ]
                if mixed
                else []
            )
            standard_results, direct_results = await asyncio.gather(
                asyncio.gather(*standard), asyncio.gather(*direct)
            )
            print(
                json.dumps(
                    dict(
                        mixed=mixed,
                        standard=summary(standard_results),
                        direct=summary(direct_results) if mixed else None,
                    )
                ),
                flush=True,
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--standard", required=True)
    parser.add_argument("--direct", required=True)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path(__file__).with_name("munich-route-annotations.json"),
    )
    parser.add_argument("--samples", type=int, default=25)
    parser.add_argument("--rate", type=float, default=2)
    args = parser.parse_args()
    if args.samples < 1 or args.rate <= 0:
        parser.error("samples and rate must be positive")
    asyncio.run(run(args))
