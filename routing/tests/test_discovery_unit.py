import json
import sys
import unittest
from pathlib import Path
from lupa import LuaRuntime
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_secret_tips import lua_lookup


class DiscoveryUnitTest(unittest.TestCase):
    def test_v20_lookup_deduplicates_way_ids_and_ignores_other_categories(self):
        contents = json.dumps({'type':'FeatureCollection', 'features': [
            {'properties':{'osm_id':value, 'munichways_neuralgic_point':kind}}
            for value,kind in [(123,'Geheimtipp'),('123','Geheimtipp'),(456,'Gefahr'),('-', 'Geheimtipp')]
        ]}).encode()
        lua = LuaRuntime()
        lookup = lua.execute(lua_lookup(contents))
        self.assertTrue(lookup[123])
        self.assertIsNone(lookup[456])
        with self.assertRaises(ValueError): lua_lookup(b'{"type":"FeatureCollection","features":[]}')

    def test_real_discovery_lua_changes_only_allowed_cycling_rates(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute("""
          mode={cycling=1,pushing_bike=2,inaccessible=0}
          package.preload['secret_tips']=function() return {[123]=true} end
          package.preload['bike']=function() return {
            setup=function() return {} end, process_way=function() end,
            process_node=function() end, process_turn=function() end,
            get_cycling_tag=function(way,key,forward) return way:get_value_by_key(key) end
          } end
        """)
        profile = lua.execute((Path(__file__).resolve().parents[1]/'discovery.lua').read_text())
        make = lua.eval('function(tags,id) return {id=function() return id end, get_value_by_key=function(self,key) return tags[key] end} end')
        def rate(tags, way_id=1, mode=1, original_rate=10):
            result = lua.table_from({'forward_mode':mode,'backward_mode':0,'forward_rate':original_rate,'backward_rate':0,'forward_speed':20,'backward_speed':0})
            profile.process_way(lua.table(), make(lua.table_from(tags),way_id), result)
            self.assertEqual(20,result.forward_speed)
            self.assertEqual(0,result.backward_rate)
            return result.forward_rate
        green={'highway':'cycleway','class:bicycle':'3'}
        main={'highway':'primary','class:bicycle':'-1'}
        self.assertGreater(rate(green), rate(main))
        self.assertAlmostEqual(rate(green,123), rate(green)*1.2)
        self.assertEqual(0,rate(green,123,0,0))
        self.assertEqual(10,rate(green,123,2))
        self.assertEqual(10,rate({'highway':'steps'},123))
        self.assertLess(rate(dict(green,surface='gravel')),rate(dict(green,surface='fine_gravel')))
