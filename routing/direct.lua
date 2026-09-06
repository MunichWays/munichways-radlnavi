-- Shortest traversable bicycle route, sharing access and guidance with bike.lua.
-- Edge weights are metres; actual speeds and turn durations remain available
-- for ETA and turn-by-turn navigation. Comfort is analyzed independently.
local bicycle = require('bike')

local function setup_direct()
  local profile = bicycle.setup()
  profile.properties.weight_name = 'distance'
  return profile
end

local function process_direct_way(profile, way, result)
  bicycle.process_way(profile, way, result)

  -- This rating is an explicit exclusion in the existing standard profile.
  -- Removing comfort preferences must not reopen these excluded ways.
  if way:get_value_by_key('class:bicycle') == '-3' then
    result.forward_mode = mode.inaccessible
    result.backward_mode = mode.inaccessible
    result.forward_speed = 0
    result.backward_speed = 0
    result.forward_rate = 0
    result.backward_rate = 0
    return
  end

  -- OSRM distance weighting: length / rate, without comfort/sidepath bonuses.
  -- Discard fixed time-based weights (e.g. ferries), retaining their durations.
  result.weight = -1
  if result.forward_mode ~= mode.inaccessible and result.forward_speed > 0 then
    result.forward_rate = 1
  end
  if result.backward_mode ~= mode.inaccessible and result.backward_speed > 0 then
    result.backward_rate = 1
  end
end

local function process_direct_turn(profile, turn)
  bicycle.process_turn(profile, turn)
  -- Seconds of delay affect ETA, not metres in the shortest-path objective.
  turn.weight = 0
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
