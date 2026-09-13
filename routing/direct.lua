-- Fast rideable bicycle route, sharing access, physical speeds and guidance with
-- bike.lua. Comfort ratings do not influence this profile. Stairs and pushing
-- remain last-resort connections with the shared penalties; ferries are excluded.
local bicycle = require('bike')

-- Conservative selection preferences, separate from the shared travel-time
-- model. Good paved cycleways remain on equal terms with asphalt main roads.
local surface_costs = {
  compacted = 1.05,
  fine_gravel = 1.05,
  cobblestone = 1.15,
  sett = 1.15,
  unhewn_cobblestone = 1.15,
  gravel = 1.25,
  unpaved = 1.25,
  earth = 1.25,
  dirt = 1.25,
  ground = 1.25,
  grass = 1.25,
  grass_paver = 1.25,
  woodchips = 1.25,
  mud = 1.50,
  sand = 1.50,
}

local function setup_direct()
  local profile = bicycle.setup()
  profile.properties.weight_name = 'fast_cycling'
  -- Signals remain fully represented in ETA, but have less influence on route
  -- selection. This avoids detours chosen mainly to save one estimated wait.
  profile.traffic_light_weight_factor = 0.25
  return profile
end

local function exclude_direction(result, direction)
  result[direction .. '_mode'] = mode.inaccessible
  result[direction .. '_speed'] = 0
  result[direction .. '_rate'] = 0
end

local function process_direct_way(profile, way, result)
  bicycle.process_way(profile, way, result)

  local highway = way:get_value_by_key('highway')
  local road_cost = highway == 'residential' and 1.08 or 1
  local surface_cost = surface_costs[way:get_value_by_key('surface')] or 1
  local cycling_cost = road_cost * surface_cost
  if way:get_value_by_key('route') == 'ferry' then
    exclude_direction(result, 'forward')
    exclude_direction(result, 'backward')
    return
  end

  -- bike.lua has already enforced access, conditional restrictions, one-ways
  -- and use_sidepath. Keep its pushing modes and allowed start modes intact.
  if result.forward_mode == mode.ferry then
    exclude_direction(result, 'forward')
  end
  if result.backward_mode == mode.ferry then
    exclude_direction(result, 'backward')
  end

  -- Replace comfort rates with time-based rates and Direct selection costs.
  -- Speeds retain the shared surface, smoothness and maxspeed rules, so
  -- identical edges retain identical travel time in both variants.
  if result.forward_mode ~= mode.inaccessible and result.forward_speed > 0 then
    local cost = result.forward_mode == mode.cycling and cycling_cost or 1
    result.forward_rate = result.forward_speed / 3.6 / cost
  end
  if result.backward_mode ~= mode.inaccessible and result.backward_speed > 0 then
    local cost = result.backward_mode == mode.cycling and cycling_cost or 1
    result.backward_rate = result.backward_speed / 3.6 / cost
  end
  -- Same reference speed and penalties as Standard, without comfort ratings.
  -- Cap the rate (search preference), never the physical speed (travel time).
  -- Stairs that also require pushing receive the stronger cap, not both multiplied.
  if highway == 'steps' then
    local stair_rate = profile.default_speed / 3.6 / profile.steps_distance_penalty
    result.forward_rate = math.min(result.forward_rate, stair_rate)
    result.backward_rate = math.min(result.backward_rate, stair_rate)
  end
  local pushing_rate = profile.default_speed / 3.6 / profile.pushing_distance_penalty
  if result.forward_mode == mode.pushing_bike then
    result.forward_rate = math.min(result.forward_rate, pushing_rate)
  end
  if result.backward_mode == mode.pushing_bike then
    result.backward_rate = math.min(result.backward_rate, pushing_rate)
  end
  if result.duration > 0 then
    local cost = (result.forward_mode == mode.cycling or result.backward_mode == mode.cycling)
      and cycling_cost or 1
    result.weight = result.duration * cost
  else
    result.weight = -1
  end
end

local function process_direct_turn(profile, turn)
  bicycle.process_turn(profile, turn)
  -- Preserve the standard profile's mandatory-sidepath access protection.
  if not turn.source_restricted and turn.target_restricted then
    turn.weight = constants.max_turn_weight
  end
end

return {
  setup = setup_direct,
  process_way = process_direct_way,
  process_node = bicycle.process_node,
  process_turn = process_direct_turn
}
