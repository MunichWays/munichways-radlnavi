import copy
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError, URLError
from urllib.request import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_direct_deployment import check, fetch_json
from sync_direct_api import sync


class DeploymentContractTest(unittest.TestCase):
    def test_iam_propagation_and_transient_errors_retry_the_same_request(self):
        for error in (
            HTTPError("http://test", 403, "Forbidden", {}, None),
            HTTPError("http://test", 503, "Unavailable", {}, None),
            URLError("connection reset"),
        ):
            with self.subTest(error=error):
                clock = [0.0]

                def sleep(seconds):
                    clock[0] += seconds

                opener = Mock(side_effect=[error, io.BytesIO(b'{"ok":true}')])
                request = Request("http://test", data=b'{"variant":"direct"}')
                result = fetch_json(
                    request,
                    deadline=60,
                    opener=opener,
                    now=lambda: clock[0],
                    sleep=sleep,
                )
                self.assertEqual({"ok": True}, result)
                self.assertEqual(5, clock[0])
                self.assertTrue(
                    all(call.args[0] is request for call in opener.call_args_list)
                )

    def test_persistent_forbidden_fails_within_retry_budget(self):
        clock = [0.0]

        def sleep(seconds):
            clock[0] += seconds

        opener = Mock(side_effect=HTTPError("http://test", 403, "Forbidden", {}, None))
        with self.assertRaises(HTTPError):
            fetch_json(
                Request("http://test"),
                deadline=18,
                opener=opener,
                now=lambda: clock[0],
                sleep=sleep,
            )
        self.assertEqual(3, opener.call_count)
        self.assertLessEqual(clock[0], 18)
        self.assertEqual(3, opener.call_args.kwargs["timeout"])

    def test_permanent_error_or_invalid_json_is_not_retried(self):
        for outcome, error_type in (
            (HTTPError("http://test", 400, "Bad request", {}, None), HTTPError),
            (io.BytesIO(b"not-json"), ValueError),
        ):
            opener = Mock(side_effect=[outcome])
            sleeper = Mock()
            with self.assertRaises(error_type):
                fetch_json(
                    Request("http://test"),
                    deadline=60,
                    opener=opener,
                    now=lambda: 0,
                    sleep=sleeper,
                )
            opener.assert_called_once()
            sleeper.assert_not_called()

    def test_expired_shared_deadline_does_not_start_another_request(self):
        opener = Mock()
        with self.assertRaises(TimeoutError):
            fetch_json(
                Request("http://test"), deadline=10, opener=opener, now=lambda: 10
            )
        opener.assert_not_called()

    def responses(self):
        leg = {
            "steps": [{"maneuver": {"type": "arrive"}}],
            "annotation": {"nodes": [1, 2], "distance": [20]},
        }
        return [
            {"default": "direct"},
            {
                "code": "Ok",
                "waypoints": [{"location": [11, 48]}] * 3,
                "routes": [
                    {
                        "weight_name": "distance",
                        "geometry": {"type": "LineString"},
                        "legs": [copy.deepcopy(leg), copy.deepcopy(leg)],
                    }
                ],
            },
            {"ok": True, "comfort": {"index": None, "sufficientCoverage": False}},
        ]

    def test_accepts_low_coverage_and_sends_exact_leg_context(self):
        fetch = Mock(side_effect=self.responses())
        check(fetch)
        path, body = fetch.call_args.args
        self.assertEqual("/tag_distribution", path)
        self.assertEqual("direct", body["variant"])
        self.assertEqual(2, len(body["legs"]))
        self.assertEqual([20], body["legs"][0]["distance"])
        self.assertIn("start", body["legs"][0])

    def test_rejects_standard_worker_or_profile(self):
        responses = self.responses()
        responses[0]["default"] = "standard"
        with self.assertRaises(ValueError):
            check(Mock(side_effect=responses))
        responses = self.responses()
        responses[1]["routes"][0]["weight_name"] = "cyclability"
        with self.assertRaises(ValueError):
            check(Mock(side_effect=responses))

    def test_rejects_broken_navigation_or_analysis(self):
        for broken in ("navigation", "analysis"):
            responses = self.responses()
            if broken == "navigation":
                responses[1]["routes"][0]["legs"][1]["steps"] = []
            else:
                responses[2] = {"ok": False}
            with self.assertRaises(ValueError):
                check(Mock(side_effect=responses))

    def test_backend_update_preserves_direct_configuration(self):
        service = {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "env": [
                                    {
                                        "name": "PUBLIC_DIRECT_API_URL",
                                        "value": "https://direct.example",
                                    },
                                    {
                                        "name": "CORS_ORIGINS",
                                        "value": "https://frontend.example",
                                    },
                                ]
                            }
                        ]
                    }
                }
            }
        }
        run = Mock(side_effect=[json.dumps(service), "updated"])
        self.assertTrue(
            sync("project", "region", "standard", "direct", "image:commit", run=run)
        )
        command = run.call_args.args[0]
        self.assertEqual(["gcloud", "run", "services", "update", "direct"], command[:5])
        self.assertIn("--image=image:commit", command)
        self.assertIn(
            "--update-env-vars=CORS_ORIGINS=https://frontend.example", command
        )
        self.assertFalse(
            any(
                "OSRM_BACKEND_URL" in part or "--set-env-vars" in part
                for part in command
            )
        )

    def test_backend_update_leaves_disabled_direct_alone(self):
        service = {"spec": {"template": {"spec": {"containers": [{}]}}}}
        run = Mock(return_value=json.dumps(service))
        self.assertFalse(
            sync("project", "region", "standard", "direct", "image:commit", run=run)
        )
        run.assert_called_once()
