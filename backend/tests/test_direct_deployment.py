import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_direct_deployment import check
from sync_direct_api import sync


class DeploymentContractTest(unittest.TestCase):
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
