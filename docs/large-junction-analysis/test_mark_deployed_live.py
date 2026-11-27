"""mark_deployed_live: only junctions production serves exactly as activated become live."""
import unittest

import mark_deployed_live as live


def site(sid, **extra):
    return dict(dict(id=sid, number=1, name=sid, status='confirmed', evidenceCurrent=True,
                     deploymentStatus='branch-ready', polygon=[[0, 0], [1, 0], [0, 1], [0, 0]]), **extra)


def junction(sid, moves=2):
    return dict(id=sid, enabled=True, polygon=dict(type='Polygon', coordinates=[[[0, 0], [1, 0], [0, 1], [0, 0]]]),
                movements=[dict(id=f'm{i}', enabled=True) for i in range(moves)] + [dict(id='r', enabled=False)])


class LiveCandidateTests(unittest.TestCase):
    def found(self, sites, served, branch):
        return [(s['id'], n) for s, n in live.live_candidates(dict(sites=sites), served, branch)]

    def test_served_unchanged_becomes_live_with_enabled_count(self):
        j = junction('a', 3)
        self.assertEqual(self.found([site('a')], {'a': j}, {'a': j}), [('a', 3)])

    def test_branch_only_replacement_stays_branch_ready(self):
        # K110 case: production still serves the old geometry, the branch already the new one.
        self.assertEqual(self.found([site('a')], {'a': junction('a', 2)}, {'a': junction('a', 3)}), [])

    def test_not_served_unconfirmed_stale_or_already_live_are_skipped(self):
        j = junction('a')
        self.assertEqual(self.found([site('a')], {}, {'a': j}), [])
        for extra in (dict(status='open'), dict(evidenceCurrent=False), dict(deploymentStatus='live'),
                      dict(polygon=[[9, 9], [1, 0], [0, 1], [9, 9]])):
            self.assertEqual(self.found([site('a', **extra)], {'a': j}, {'a': j}), [], extra)


if __name__ == '__main__':
    unittest.main()
