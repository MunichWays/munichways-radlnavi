-- Speech metadata only: never change access, speed, weight or turn penalties.
local M = {}
local roads = {
  living_street = true, residential = true, unclassified = true, road = true,
  tertiary = true, tertiary_link = true, secondary = true, secondary_link = true,
  primary = true, primary_link = true, trunk = true, trunk_link = true,
  motorway = true, motorway_link = true
}

local function value(way, key)
  local result = way:get_value_by_key(key)
  return result ~= '' and result or nil
end

local function side_value(way, side, suffix)
  return value(way, 'cycleway:' .. side .. suffix)
    or value(way, 'cycleway:both' .. suffix)
    or value(way, 'cycleway' .. suffix)
end

function M.classify(way, forward)
  local highway = value(way, 'highway')
  if highway == 'cycleway' or highway == 'path' then return 'cycleway' end
  -- In particular, footway, track and service do not establish a transition.
  if not roads[highway] then return nil end

  local left_driving = value(way, 'driving_side') == 'left'
  for _, side in ipairs({'right', 'left'}) do
    local along_way = (side == 'right') ~= left_driving
    local road_oneway = value(way, 'oneway')
    if road_oneway == 'yes' or road_oneway == '1' then along_way = true end
    if road_oneway == '-1' then along_way = false end
    local oneway = side_value(way, side, ':oneway')
    -- Explicit values are relative to OSM way order, not to the road side.
    if oneway == 'yes' or oneway == '1' then along_way = true end
    if oneway == '-1' then along_way = false end
    if (oneway == 'no' or along_way == forward)
      and side_value(way, side, '') == 'lane'
      and side_value(way, side, ':lane') == 'exclusive' then
      return 'cycleway'
    end
  end
  return 'road'
end

function M.apply(way, result)
  for _, direction in ipairs({'forward', 'backward'}) do
    if result[direction .. '_mode'] == mode.cycling then
      local class = M.classify(way, direction == 'forward')
      if class then result[direction .. '_classes'][class] = true end
    end
  end
end

return M
