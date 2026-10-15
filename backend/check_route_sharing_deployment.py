"""Fail deployment when the configured route store cannot be read.

A missing route must produce 404. Missing configuration, IAM or bucket access
instead produces 503. No test routes or user data are created by this check.
"""
import argparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def check(endpoint, opener=urlopen):
    request = Request(endpoint.rstrip('/') + '/shared_routes/' + 'a' * 32)
    try:
        with opener(request, timeout=30) as response:
            status = response.status
    except HTTPError as error:
        status = error.code
    if status not in (200, 404):
        raise RuntimeError(
            f'Route storage check failed (HTTP {status}). Run '
            'backend/configure_route_sharing.ps1 once with project-admin '
            'credentials, then redeploy. The bucket must be private, have a '
            '90-day lifecycle, and allow the API service account to read/write.'
        )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', required=True)
    check(parser.parse_args().endpoint)
    print('Route sharing storage is reachable')
