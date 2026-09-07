import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_direct_enabled import direct_enabled


class DirectEnabledTest(unittest.TestCase):
    def test_enabled_and_disabled_use_public_capability(self):
        for enabled in (True, False):
            with self.subTest(enabled=enabled):
                fetch = Mock(
                    return_value=io.BytesIO(
                        json.dumps(
                            {"default": "standard", "direct": {"available": enabled}}
                        ).encode()
                    )
                )
                self.assertIs(enabled, direct_enabled("https://api.example/", fetch))
                fetch.assert_called_once_with(
                    "https://api.example/routing_variants", timeout=30
                )

    def test_invalid_capability_is_not_silently_treated_as_disabled(self):
        for payload in (
            {},
            [],
            {"default": "direct", "direct": {"available": True}},
            {"default": "standard", "direct": {"available": "false"}},
            {"default": "standard", "direct": {"available": 0}},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                direct_enabled(
                    "https://api.example",
                    Mock(return_value=io.BytesIO(json.dumps(payload).encode())),
                )

    def test_http_and_network_failures_do_not_skip_refresh(self):
        for error in (
            HTTPError("https://api.example", 503, "unavailable", {}, None),
            URLError("connection failed"),
            TimeoutError(),
        ):
            with self.subTest(error=error), self.assertRaises(type(error)):
                direct_enabled("https://api.example", Mock(side_effect=error))

    def test_invalid_json_fails_the_check(self):
        with self.assertRaises(ValueError):
            direct_enabled(
                "https://api.example", Mock(return_value=io.BytesIO(b"not json"))
            )
