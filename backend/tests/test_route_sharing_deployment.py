import sys
import unittest
from pathlib import Path
from unittest.mock import Mock
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_route_sharing_deployment import check


class RouteSharingDeploymentTest(unittest.TestCase):
    def test_missing_route_proves_storage_is_reachable_without_creating_data(self):
        opener = Mock(side_effect=HTTPError('http://test', 404, '', {}, None))
        check('https://api.example/', opener=opener)
        request = opener.call_args.args[0]
        self.assertEqual('GET', request.get_method())
        self.assertEqual('https://api.example/shared_routes/' + 'a' * 32, request.full_url)

    def test_missing_configuration_and_storage_permissions_fail_deployment(self):
        for status in [403, 500, 503]:
            with self.subTest(status=status), self.assertRaisesRegex(RuntimeError, 'configure_route_sharing'):
                check('https://api.example', opener=Mock(
                    side_effect=HTTPError('http://test', status, '', {}, None)))


if __name__ == '__main__':
    unittest.main()
