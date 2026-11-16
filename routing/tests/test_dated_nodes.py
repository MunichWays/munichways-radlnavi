"""Exercise dated OSM entrances through the actual Lua node handler."""

from pathlib import Path
import unittest

from lupa import LuaRuntime


ROOT = Path(__file__).resolve().parents[1]


class DatedNodeTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.globals().routing_root = ROOT.as_posix()
        self.lua.execute("""
            package.path = routing_root .. '/?.lua;' .. package.path
            for _, name in ipairs({'lib/set', 'lib/sequence', 'lib/way_handlers',
                                   'lib/maxspeed'}) do
                package.preload[name] = function() return {} end
            end
            package.preload['lib/access'] = function() return {
                find_access_tag = function(node, hierarchy)
                    for _, key in ipairs(hierarchy) do
                        local value = node:get_value_by_key(key)
                        if value and value ~= '' then return value end
                    end
                end
            } end
            package.preload['secret_tips'] = function() return {} end
            obstacle_direction = {both=0, forward=1, backward=2}
            test_date = '2026-11-16'
            os.getenv = function(key)
                if key == 'RADLNAVI_ROUTING_DATE' then return test_date end
            end
            function make_node(tags)
                return {get_value_by_key=function(self, key) return tags[key] end}
            end
        """)
        self.profile = self.lua.eval("require('bike')")[0]
        self.settings = self.lua.eval("""{
            access_tags_hierarchy={'bicycle', 'vehicle', 'access'},
            access_tag_blacklist={no=true, private=true},
            barrier_whitelist={cycle_barrier=true}
        }""")

    def blocked(self, tags, date='2026-11-16'):
        self.lua.globals().test_date = date
        result = self.lua.table()
        node = self.lua.globals().make_node(self.lua.table_from(tags))
        self.profile.process_node(self.settings, node, result)
        return result.barrier is True

    def test_original_ow1_entrance_no_longer_splits_strasse_5(self):
        tags = {'bicycle': 'no', 'foot': 'yes', 'temporary:entrance': 'yes',
                'start_date': '2018-09-22', 'end_date': '2018-10-07'}
        self.assertFalse(self.blocked(tags))
        self.assertTrue(self.blocked(tags, '2018-09-22'))
        self.assertTrue(self.blocked(tags, '2018-10-07'))
        self.assertFalse(self.blocked(tags, '2018-10-08'))

    def test_advanced_event_dates_only_block_during_event(self):
        tags = {'bicycle': 'no', 'start_date': '2027-09-18',
                'end_date': '2027-10-03'}
        for date, blocked in [('2027-09-17', False), ('2027-09-18', True),
                              ('2027-10-03', True), ('2027-10-04', False)]:
            with self.subTest(date=date):
                self.assertEqual(blocked, self.blocked(tags, date))

    def test_end_date_alone_and_expired_barriers(self):
        for tags in ({'bicycle': 'no'}, {'access': 'private'}, {'barrier': 'fence'}):
            self.assertTrue(self.blocked(tags))
            self.assertFalse(self.blocked({**tags, 'end_date': '2026-11-15'}))
            self.assertTrue(self.blocked({**tags, 'end_date': '2026-11-16'}))

    def test_invalid_or_partial_dates_do_not_remove_restrictions(self):
        for value in ('', '2018', '2018-10', '2018-02-29', '2026-04-31',
                      '0000-01-01', 'unknown'):
            with self.subTest(value=value):
                self.assertTrue(self.blocked({'bicycle': 'no', 'end_date': value}))
        self.assertTrue(self.blocked({'bicycle': 'no', 'start_date': '2027-01-01',
                                     'end_date': '2018-01-01'}))
        self.assertFalse(self.blocked({'bicycle': 'no', 'end_date': '2024-02-29'}))

    def test_seasonal_conditions_keep_existing_behavior(self):
        self.lua.execute((ROOT / 'test_conditional_access.lua').read_text())

    def test_all_profiles_share_dated_node_handling(self):
        for name in ('direct', 'discovery'):
            with self.subTest(profile=name):
                self.lua.globals().test_profile = name
                self.assertTrue(self.lua.eval(
                    "require(test_profile).process_node == require('bike').process_node"))

    def test_import_date_is_validated_and_shared_with_seasonal_access(self):
        module = self.lua.eval("require('conditional_access')")
        self.lua.globals().test_date = '2024-02-29'
        self.assertEqual(20240229, module.routing_date())
        self.assertEqual(229, module.routing_month_day())
        self.lua.execute("os.date = function() return '2026-11-16' end")
        for value in ('2026-02-29', 'build-uuid', ''):
            self.lua.globals().test_date = value
            self.assertEqual(20261116, module.routing_date())


if __name__ == '__main__':
    unittest.main()
