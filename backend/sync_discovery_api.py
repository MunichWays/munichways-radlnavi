"""Keep an enabled discovery worker on the same backend image after API updates."""

import argparse
import json
import subprocess


def sync(project, region, standard, discovery, image, run=subprocess.check_output):
    common = [f"--project={project}", f"--region={region}"]
    service = json.loads(
        run(
            [
                "gcloud",
                "run",
                "services",
                "describe",
                standard,
                *common,
                "--format=json",
            ],
            text=True,
        )
    )
    env = {
        item["name"]: item.get("value", "")
        for item in service["spec"]["template"]["spec"]["containers"][0].get("env", [])
    }
    if not (env.get("PUBLIC_DISCOVERY_API_URL") or env.get("DISCOVERY_API_URL")):
        return False
    command = [
        "gcloud",
        "run",
        "services",
        "update",
        discovery,
        *common,
        f"--image={image}",
    ]
    if "CORS_ORIGINS" in env:
        command.append(f"--update-env-vars=CORS_ORIGINS={env['CORS_ORIGINS']}")
    # Preserve discovery OSRM URL/audience, ROUTING_VARIANT and graph version.
    run(command, text=True)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("project", "region", "standard", "discovery", "image"):
        parser.add_argument(f"--{argument}", required=True)
    changed = sync(**vars(parser.parse_args()))
    print(
        "Discovery API image synchronized"
        if changed
        else "Discovery API is not enabled; skipped"
    )
