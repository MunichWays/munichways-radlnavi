import json
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from configure_discovery_warmup import configure, minimum_instances, scheduler_account

PROJECT = "test-project"
REGION = "europe-west3"
API = "munichways-radlnavi-discovery-api"
ROUTING = "munichways-radlnavi-discovery-routing"


def option(command, name):
    return next(
        item.split("=", 1)[1] for item in command if item.startswith(name + "=")
    )


def scheduled_commands(run):
    return [
        call.args[0]
        for call in run.call_args_list
        if call.args[0][:3] == ["gcloud", "scheduler", "jobs"]
        and call.args[0][3] != "list"
    ]


def service_commands(run):
    return [
        call.args[0]
        for call in run.call_args_list
        if call.args[0][:4] == ["gcloud", "run", "services", "update"]
    ]


class DiscoveryWarmupTest(unittest.TestCase):
    def test_night_boundaries_summer_winter_and_dst_are_berlin_local_time(self):
        examples = {
            "2026-11-03T22:59:59+00:00": 1,  # 23:59:59 CET
            "2026-11-03T23:00:00+00:00": 0,  # midnight CET
            "2026-11-04T03:59:59+00:00": 0,
            "2026-11-04T04:00:00+00:00": 1,  # 05:00 CET
            "2026-07-01T21:59:59+00:00": 1,  # 23:59:59 CEST
            "2026-07-01T22:00:00+00:00": 0,
            "2026-07-02T02:59:59+00:00": 0,
            "2026-07-02T03:00:00+00:00": 1,  # 05:00 CEST
            "2026-03-29T00:59:59+00:00": 0,  # spring: 01:59 -> 03:00
            "2026-03-29T01:00:00+00:00": 0,
            "2026-03-29T03:00:00+00:00": 1,
            "2026-10-25T00:30:00+00:00": 0,  # both autumn 02:30 occurrences
            "2026-10-25T01:30:00+00:00": 0,
            "2026-10-25T04:00:00+00:00": 1,
        }
        for timestamp, expected in examples.items():
            with self.subTest(timestamp=timestamp):
                self.assertEqual(
                    expected, minimum_instances(datetime.fromisoformat(timestamp))
                )
        with self.assertRaises(ValueError):
            minimum_instances(datetime(2026, 11, 4, 5))

    def run_setup(self, run, *, now=None, check_only=False):
        configure(
            PROJECT,
            REGION,
            API,
            ROUTING,
            run=run,
            check_only=check_only,
            now=now or (lambda: datetime.fromisoformat("2026-11-04T12:00:00+00:00")),
        )

    def test_schedules_use_oauth_and_change_only_discovery_minimum_not_availability(
        self,
    ):
        run = Mock(side_effect=["account", "[]", "", "", "", "", "", ""])
        self.run_setup(run)
        commands = scheduled_commands(run)
        self.assertEqual(4, len(commands))
        for command in commands:
            name = command[5]
            minimum = 0 if name.endswith("cool-night") else 1
            self.assertEqual("create", command[3])
            self.assertEqual(
                "0 0 * * *" if minimum == 0 else "0 5 * * *",
                option(command, "--schedule"),
            )
            self.assertEqual("Europe/Berlin", option(command, "--time-zone"))
            self.assertEqual("PUT", option(command, "--http-method"))
            self.assertIn("X-HTTP-Method-Override=PATCH", option(command, "--headers"))
            self.assertEqual(
                scheduler_account(PROJECT),
                option(command, "--oauth-service-account-email"),
            )
            body = json.loads(option(command, "--message-body"))
            self.assertEqual({"scaling": {"minInstanceCount": minimum}}, body)
            service = name.rsplit("-", 2)[0]
            self.assertIn(service, (API, ROUTING))
            self.assertEqual(
                f"https://run.googleapis.com/v2/projects/{PROJECT}/locations/{REGION}"
                f"/services/{service}?update_mask=scaling.minInstanceCount",
                option(command, "--uri"),
            )
            self.assertIn("--max-retry-duration=600s", command)
        self.assertTrue(
            all(command[5].endswith("cool-night") for command in commands[:2])
        )
        for command in service_commands(run):
            self.assertIn(command[4], (API, ROUTING))
            self.assertIn("--min=1", command)
            self.assertIn("--min-instances=0", command)
            self.assertFalse(
                any(
                    item.startswith("--scaling=") or item.startswith("--image=")
                    for item in command
                )
            )
        self.assertEqual(2, len(service_commands(run)))

    def test_repeated_deploy_updates_existing_jobs_and_preserves_unrelated_jobs(self):
        jobs = [
            {
                "name": f"projects/{PROJECT}/locations/{REGION}/jobs/{service}-{suffix}",
                "state": "ENABLED",
            }
            for service in (API, ROUTING)
            for suffix in ("warm-day", "cool-night")
        ]
        jobs.append(
            {
                "name": "projects/test/locations/region/jobs/another-job",
                "state": "PAUSED",
            }
        )
        run = Mock(side_effect=["account", json.dumps(jobs), "", "", "", "", "", ""])
        self.run_setup(run)
        commands = scheduled_commands(run)
        self.assertEqual(4, len(commands))
        for command in commands:
            self.assertEqual("update", command[3])
            self.assertIn(
                "--update-headers=Content-Type=application/json,X-HTTP-Method-Override=PATCH",
                command,
            )

    def test_deploy_crossing_a_boundary_reconciles_both_services_to_the_new_window(
        self,
    ):
        for first, second, expected in (
            ("2026-11-03T22:59:59+00:00", "2026-11-03T23:00:00+00:00", [1, 1, 0, 0]),
            ("2026-11-04T03:59:59+00:00", "2026-11-04T04:00:00+00:00", [0, 0, 1, 1]),
        ):
            with self.subTest(first=first):
                run = Mock(
                    side_effect=["account", "[]", "", "", "", "", "", "", "", ""]
                )
                clock = Mock(
                    side_effect=[
                        datetime.fromisoformat(first),
                        datetime.fromisoformat(second),
                        datetime.fromisoformat(second),
                    ]
                )
                self.run_setup(run, now=clock)
                commands = service_commands(run)
                self.assertEqual(
                    [str(value) for value in expected],
                    [option(command, "--min") for command in commands],
                )
                self.assertEqual(
                    [ROUTING, API], [command[4] for command in commands[-2:]]
                )
                self.assertEqual(3, clock.call_count)

    def test_night_deploy_keeps_both_minima_at_zero(self):
        run = Mock(side_effect=["account", "[]", "", "", "", "", "", ""])
        self.run_setup(
            run, now=lambda: datetime.fromisoformat("2026-11-04T02:00:00+00:00")
        )
        self.assertEqual(
            ["0", "0"], [option(command, "--min") for command in service_commands(run)]
        )

    def test_preflight_checks_without_mutations_or_reading_clock(self):
        run = Mock(side_effect=["account", "[]"])
        clock = Mock(
            side_effect=AssertionError("preflight cannot choose a deployment minimum")
        )
        self.run_setup(run, now=clock, check_only=True)
        self.assertEqual(2, run.call_count)
        self.assertFalse(scheduled_commands(run))
        self.assertFalse(service_commands(run))

    def test_missing_permissions_are_not_treated_as_missing_jobs(self):
        for failure_at in (0, 1):
            run = Mock(
                side_effect=(
                    ["account"][:failure_at]
                    + [subprocess.CalledProcessError(1, "gcloud")]
                )
            )
            with self.subTest(failure_at=failure_at):
                with self.assertRaises(subprocess.CalledProcessError):
                    self.run_setup(run)
                self.assertFalse(scheduled_commands(run))
                self.assertFalse(service_commands(run))

    def test_paused_or_disabled_owned_jobs_fail_before_mutations(self):
        for state in ("PAUSED", "DISABLED"):
            run = Mock(
                side_effect=[
                    "account",
                    json.dumps(
                        [
                            {
                                "name": f"projects/test/locations/region/jobs/{API}-cool-night",
                                "state": state,
                            }
                        ]
                    ),
                ]
            )
            with self.subTest(state=state):
                with self.assertRaisesRegex(RuntimeError, state):
                    self.run_setup(run)
                self.assertFalse(scheduled_commands(run))
                self.assertFalse(service_commands(run))

    def test_partial_setup_failure_does_not_warm_instances_and_retry_recovers(self):
        # Both night schedules were created; the first morning schedule failed.
        run = Mock(
            side_effect=[
                "account",
                "[]",
                "",
                "",
                subprocess.CalledProcessError(1, "gcloud"),
            ]
        )
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_setup(run)
        self.assertFalse(service_commands(run))
        jobs = [
            {
                "name": f"projects/test/locations/region/jobs/{service}-cool-night",
                "state": "ENABLED",
            }
            for service in (API, ROUTING)
        ]
        retry = Mock(side_effect=["account", json.dumps(jobs), "", "", "", "", "", ""])
        self.run_setup(retry)
        self.assertEqual(
            ["update", "update", "create", "create"],
            [command[3] for command in scheduled_commands(retry)],
        )
        self.assertEqual(2, len(service_commands(retry)))


if __name__ == "__main__":
    unittest.main()
