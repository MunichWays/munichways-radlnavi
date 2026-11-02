-- Relaxed exploration: inherit every access, speed and guidance rule from Standard.
local bicycle = require('bike')
local secret_tips = require('secret_tips')
local class_factors = { ['-2']=0.45, ['-1']=0.65, ['0']=0.85, ['1']=1.10, ['2']=1.35, ['3']=1.55 }
-- Highway is a preference proxy, not proof of greenery or traffic volume.
local highway_factors = {
  cycleway=1.20, path=1.15, living_street=1.10, residential=1,
  service=0.95, track=0.95, unclassified=0.85, tertiary=0.75,
  secondary=0.55, primary=0.40, trunk=0.30,
  tertiary_link=0.75, secondary_link=0.55, primary_link=0.40, trunk_link=0.30,
}
local surface_factors = { compacted=0.95, fine_gravel=0.95, gravel=0.75,
  unpaved=0.80, ground=0.75, dirt=0.75, grass=0.60, mud=0.45, sand=0.45 }

local function setup()
  local profile = bicycle.setup()
  profile.properties.weight_name = 'relaxed_cycling'
  return profile
end

local function process_way(profile, way, result)
  bicycle.process_way(profile, way, result)
  local highway = way:get_value_by_key('highway')
  local factor = (class_factors[way:get_value_by_key('class:bicycle')] or 0.85)
    * (highway_factors[highway] or 0.85)
  if secret_tips[tonumber(way:id())] then factor = factor * 1.20 end
  for _, direction in ipairs({'forward', 'backward'}) do
    -- Never reopen exclusions or reduce stairs/pushing penalties.
    if result[direction .. '_mode'] == mode.cycling and highway ~= 'steps'
      and result[direction .. '_rate'] > 0 then
      local forward = direction == 'forward'
      local surface = bicycle.get_cycling_tag(way, 'surface', forward)
      local smoothness = bicycle.get_cycling_tag(way, 'smoothness', forward)
      -- Modest compensation in selection only; real travel speeds stay unchanged.
      local smoothness_factor = (smoothness == 'intermediate' or smoothness == 'bad') and 1.10 or 1
      result[direction .. '_rate'] = result[direction .. '_rate'] * factor
        * (surface_factors[surface] or 1) * smoothness_factor
    end
  end
end

return { setup=setup, process_way=process_way,
  process_node=bicycle.process_node, process_turn=bicycle.process_turn }
