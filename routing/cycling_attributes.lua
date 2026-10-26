-- Resolve modeled cycling attributes, never access. Keep the shared JSON cases
-- passing in Lua and Python (backend/src/cycling_attributes.py).
local M = {}
local infrastructure = {
  lane=true, track=true, shared_lane=true, share_busway=true, shared=true, yes=true,
  opposite=true, opposite_lane=true, opposite_track=true
}
local opposite = {opposite=true, opposite_lane=true, opposite_track=true}
local excluded = {no=true, separate=true}

function M.resolve(way, key, forward)
  local function value(name)
    local v = way:get_value_by_key(name)
    return v ~= '' and v or nil
  end
  local function pair(side, attribute)
    return 'cycleway:' .. side .. ':' .. attribute,
      'cycleway:' .. attribute .. ':' .. side
  end
  if value('bicycle') == 'dismount' and key ~= 'width' then
    return {value=value(key), source=value(key) and key or nil,
      conflict=false, ambiguous=false}
  end
  local function has_attributes(side)
    -- Width must not influence the surface/smoothness used for routing.
    local attributes = key == 'width' and {'surface', 'smoothness', 'width'}
      or {'surface', 'smoothness'}
    for _, attribute in ipairs(attributes) do
      local canonical, alias = pair(side, attribute)
      if value(canonical) or value(alias) then return true end
    end
    return false
  end
  local left_driving = value('driving_side') == 'left'
  local preferred = ((forward == true) == left_driving) and 'left' or 'right'
  local candidates = {}
  local scoped, ambiguous, conflict = false, false, false
  for _, side in ipairs({'right', 'left'}) do
    local kind = value('cycleway:' .. side) or value('cycleway:both') or value('cycleway')
    local present = kind ~= nil or has_attributes(side) or has_attributes('both')
    scoped = scoped or present
    if excluded[kind] then
      local canonical, alias = pair(side, key)
      conflict = conflict or value(canonical) ~= nil or value(alias) ~= nil
    elseif present then
      if kind and not infrastructure[kind] then
        ambiguous = true
      else
        local along = (side == 'right') ~= left_driving
        local road_oneway = value('oneway')
        if road_oneway == 'yes' or road_oneway == '1' or road_oneway == 'true' then
          along = true
        elseif road_oneway == '-1' then
          along = false
        end
        if opposite[kind] then along = road_oneway == '-1' end
        local oneway = value('cycleway:' .. side .. ':oneway')
          or value('cycleway:both:oneway') or value('cycleway:oneway')
        if oneway == 'yes' or oneway == '1' or oneway == 'true' then
          along = true
        elseif oneway == '-1' then
          along = false
        end
        local twoway = oneway == 'no' or oneway == '0' or oneway == 'false'
        if oneway and not twoway and oneway ~= 'yes' and oneway ~= '1'
          and oneway ~= 'true' and oneway ~= '-1' then
          ambiguous = true
        elseif forward == nil then
          ambiguous = true
        elseif twoway or along == forward then
          table.insert(candidates, side)
        end
      end
    end
  end
  local side = nil
  for _, candidate in ipairs(candidates) do
    if candidate == preferred then side = candidate end
  end
  side = side or candidates[1]
  if side ~= preferred and ambiguous then side = nil end
  if side then
    ambiguous = false
    for _, scope in ipairs({side, 'both'}) do
      local canonical, alias = pair(scope, key)
      local first, second = value(canonical), value(alias)
      conflict = conflict or (first ~= nil and second ~= nil and first ~= second)
      if first or second then
        return {value=first or second, source=first and canonical or alias,
          side=side, conflict=conflict, ambiguous=false}
      end
    end
  end
  local common = 'cycleway:' .. key
  if (side or not scoped or ambiguous) and value(common) then
    return {value=value(common), source=common, side=side,
      conflict=conflict, ambiguous=ambiguous}
  end
  -- Total road width is not a cycle-lane width. Standalone paths retain width.
  local highway = value('highway')
  local standalone = highway == 'cycleway' or highway == 'path'
    or highway == 'footway' or highway == 'track'
  if key ~= 'width' or (standalone and not side and not scoped) then
    return {value=value(key), source=value(key) and key or nil, side=side,
      conflict=conflict, ambiguous=ambiguous}
  end
  return {side=side, conflict=conflict, ambiguous=ambiguous}
end

return M
