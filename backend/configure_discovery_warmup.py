"""Keep Discovery warm from 05:00 to 00:00 Europe/Berlin, including after deploys."""

import argparse
from datetime import datetime, timezone
import json
import subprocess
from zoneinfo import ZoneInfo

TIME_ZONE = "Europe/Berlin"


def minimum_instances(now):
    if now.tzinfo is None:
        raise ValueError("An aware deployment time is required")
    return int(now.astimezone(ZoneInfo(TIME_ZONE)).hour >= 5)


def scheduler_account(project):
    return f"radlnavi-discovery-scheduler@{project}.iam.gserviceaccount.com"


def configure(
    project,
    region,
    api,
    routing,
    *,
    check_only=False,
    run=subprocess.check_output,
    now=lambda: datetime.now(timezone.utc),
):
    ZoneInfo(TIME_ZONE)  # Verify time zone data before the graph build/mutations.
    common = [f"--project={project}", f"--location={region}"]
    account = scheduler_account(project)
    # Fail before the expensive graph build if the one-time setup is missing.
    run(
        [
            "gcloud",
            "iam",
            "service-accounts",
            "describe",
            account,
            f"--project={project}",
            "--format=value(email)",
        ],
        text=True,
    )
    jobs = json.loads(
        run(
            ["gcloud", "scheduler", "jobs", "list", *common, "--format=json"], text=True
        )
    )
    existing = {job["name"].rsplit("/", 1)[-1]: job for job in jobs}
    services = (routing, api)
    schedules = (("cool-night", "0 0 * * *", 0), ("warm-day", "0 5 * * *", 1))
    for service in services:
        for suffix, _, _ in schedules:
            job = existing.get(f"{service}-{suffix}", {})
            if job.get("state") in ("PAUSED", "DISABLED"):
                raise RuntimeError(
                    f"Discovery schedule is {job['state']}: {job['name']}; "
                    "resume it explicitly before deploying"
                )
    if check_only:
        return

    # Create only missing jobs. Permission/API failures above propagate;
    # they must never be mistaken for an empty project or a successful rollout.
    # Install both night jobs before either morning job. A partial first setup
    # must not enable recurring warm instances without a matching night job.
    for suffix, schedule, minimum in schedules:
        for service in services:
            uri = (
                f"https://run.googleapis.com/v2/projects/{project}/locations/{region}"
                f"/services/{service}?update_mask=scaling.minInstanceCount"
            )
            name = f"{service}-{suffix}"
            action = "update" if name in existing else "create"
            header_flag = "--update-headers" if action == "update" else "--headers"
            run(
                [
                    "gcloud",
                    "scheduler",
                    "jobs",
                    action,
                    "http",
                    name,
                    *common,
                    f"--schedule={schedule}",
                    f"--time-zone={TIME_ZONE}",
                    f"--uri={uri}",
                    # gcloud Scheduler has no PATCH method; Google supports this override.
                    "--http-method=PUT",
                    f"{header_flag}=Content-Type=application/json,X-HTTP-Method-Override=PATCH",
                    f"--message-body={json.dumps({'scaling': {'minInstanceCount': minimum}})}",
                    f"--oauth-service-account-email={account}",
                    "--oauth-token-scope=https://www.googleapis.com/auth/cloud-platform",
                    "--attempt-deadline=60s",
                    "--max-retry-attempts=3",
                    "--max-retry-duration=600s",
                    "--min-backoff=10s",
                    "--max-backoff=60s",
                    "--max-doublings=3",
                    "--quiet",
                ],
                text=True,
            )

    # Apply the current window, not the hour when the graph build started.
    # A Cloud Run update itself can cross 00:00/05:00; reconcile BOTH services
    # again if the window changed during those operations.
    minimum = minimum_instances(now())
    for _ in range(3):
        for service in services:
            run(
                [
                    "gcloud",
                    "run",
                    "services",
                    "update",
                    service,
                    f"--project={project}",
                    f"--region={region}",
                    f"--min={minimum}",
                    "--min-instances=0",
                    "--quiet",
                ],
                text=True,
            )
            print(f"{service}: minimum {minimum}; warm 05:00-00:00 {TIME_ZONE}")
        current = minimum_instances(now())
        if current == minimum:
            return
        minimum = current
    raise RuntimeError("Discovery scaling window kept changing during deployment")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", default="europe-west3")
    parser.add_argument("--api", default="munichways-radlnavi-discovery-api")
    parser.add_argument("--routing", default="munichways-radlnavi-discovery-routing")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = vars(parser.parse_args())
    args.pop("apply")
    configure(**args)


if __name__ == "__main__":
    main()
