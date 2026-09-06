"""Open-loop ABBA comparison; use ONLY a local or explicitly designated staging API."""

import argparse
import asyncio
import json
import math
from time import perf_counter

import httpx


def summarize(samples):
    values = sorted(item["ms"] for item in samples)
    return {
        "requests": len(samples),
        "errors": sum(item["status"] != 200 for item in samples),
        "p50_ms": values[math.ceil(len(values) * 0.5) - 1],
        "p95_ms": values[math.ceil(len(values) * 0.95) - 1],
    }


async def run(args):
    path = f"/route/v1/bike/{args.coordinates}"
    common = dict(
        steps="true",
        annotations="nodes,distance",
        geometries="geojson",
        overview="full",
        comfort="true",
    )
    async with httpx.AsyncClient(
        base_url=args.base_url, timeout=60, limits=httpx.Limits(max_connections=100)
    ) as client:

        async def request(variant, scheduled):
            await asyncio.sleep(max(0, scheduled - perf_counter()))
            try:
                target = (
                    (args.direct_base_url.rstrip("/") + path)
                    if variant == "direct" and args.direct_base_url
                    else path
                )
                response = await client.get(
                    target, params={**common, "variant": variant}
                )
                status = response.status_code
                if status == 200:
                    payload = response.json()
                    if payload.get("code") != "Ok" or not payload.get("routes", [{}])[
                        0
                    ].get("comfort"):
                        status = -2
            except (httpx.HTTPError, ValueError):
                status = -1
            # Include scheduling delay: overload must not disappear from latency.
            return {
                "ms": round((perf_counter() - scheduled) * 1000, 3),
                "status": status,
            }

        for variant in ("standard", "direct"):
            for _ in range(5):
                await request(variant, perf_counter())
        phases = []
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
            phase = {
                "mixed": mixed,
                "standard": summarize(standard_results),
                "direct": summarize(direct_results) if mixed else None,
                "standard_samples": standard_results,
                "direct_samples": direct_results,
            }
            phases.append(phase)
            print(
                json.dumps(
                    {k: v for k, v in phase.items() if not k.endswith("samples")}
                ),
                flush=True,
            )
        baseline = summarize(
            [s for p in phases if not p["mixed"] for s in p["standard_samples"]]
        )
        mixed = summarize(
            [s for p in phases if p["mixed"] for s in p["standard_samples"]]
        )
        report = {
            "configuration": vars(args),
            "baseline": baseline,
            "with_direct": mixed,
            "p95_change_percent": round(
                (mixed["p95_ms"] / baseline["p95_ms"] - 1) * 100, 2
            ),
            "phases": phases,
        }
        with open(args.output, "w", encoding="utf-8") as output:
            json.dump(report, output, indent=2)
        print(json.dumps({k: v for k, v in report.items() if k != "phases"}, indent=2))
        if any(
            p["standard"]["errors"] or (p["direct"] and p["direct"]["errors"])
            for p in phases
        ):
            raise SystemExit(
                "Benchmark contained failed requests; do not accept latency alone."
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18090")
    parser.add_argument(
        "--direct-base-url",
        help="Separate public direct API; omit to measure forwarding",
    )
    parser.add_argument(
        "--coordinates", default="11,48.6;11.001,48.6;11.002,48.6;11,48.6"
    )
    parser.add_argument("--rate", type=float, default=5)
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--output", default="variants-load.json")
    arguments = parser.parse_args()
    if arguments.rate <= 0 or arguments.samples < 1:
        parser.error("rate and samples must be positive")
    asyncio.run(run(arguments))
