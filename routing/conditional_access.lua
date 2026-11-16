local conditional_access = {}

local months = {
  jan = 1, feb = 2, mar = 3, apr = 4, may = 5, jun = 6,
  jul = 7, aug = 8, sep = 9, oct = 10, nov = 11, dec = 12
}

local days_in_month = {
  31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31
}

local function month_day(month, day)
  local month_number = months[string.lower(month)]
  local day_number = tonumber(day)

  if not month_number or not day_number or day_number < 1 or
      day_number > days_in_month[month_number] then
    return nil
  end

  return month_number * 100 + day_number
end

local function numeric_month_day(month, day)
  local month_number = tonumber(month)
  local day_number = tonumber(day)

  if not month_number or month_number < 1 or month_number > 12 or
      not day_number or day_number < 1 or
      day_number > days_in_month[month_number] then
    return nil
  end

  return month_number * 100 + day_number
end

local function split_clauses(value)
  local clauses = {}
  local start = 1
  local depth = 0

  for index = 1, #value do
    local character = string.sub(value, index, index)
    if character == "(" then
      depth = depth + 1
    elseif character == ")" then
      depth = math.max(0, depth - 1)
    elseif character == ";" and depth == 0 then
      table.insert(clauses, string.sub(value, start, index - 1))
      start = index + 1
    end
  end

  table.insert(clauses, string.sub(value, start))
  return clauses
end

local function date_range_is_active(start_date, end_date, current_date)
  if start_date <= end_date then
    return current_date >= start_date and current_date <= end_date
  end

  -- Ranges such as "Nov 01 - Mar 31" cross the end of the year.
  return current_date >= start_date or current_date <= end_date
end

local function full_date(value)
  if not value then return nil end
  local year, month, day = string.match(value, "^(%d%d%d%d)%-(%d%d)%-(%d%d)$")
  if not year then return nil end
  year, month, day = tonumber(year), tonumber(month), tonumber(day)
  if year < 1 or not numeric_month_day(month, day) then return nil end
  if month == 2 and day == 29 and
      (year % 4 ~= 0 or (year % 100 == 0 and year % 400 ~= 0)) then
    return nil
  end
  return year * 10000 + month * 100 + day
end

function conditional_access.routing_date()
  return full_date(os.getenv("RADLNAVI_ROUTING_DATE")) or
    full_date(os.date("%Y-%m-%d"))
end

-- OSM event elements remain mapped between events. Their tags only apply
-- within their dated lifetime; unknown/partial dates keep existing behavior.
function conditional_access.element_is_inactive(element, current_date)
  local start_date = full_date(element:get_value_by_key("start_date"))
  local end_date = full_date(element:get_value_by_key("end_date"))
  if start_date and end_date and start_date > end_date then return false end
  current_date = current_date or conditional_access.routing_date()
  return (end_date ~= nil and current_date > end_date) or
    (start_date ~= nil and current_date < start_date)
end

function conditional_access.routing_month_day()
  -- The override makes imports reproducible and permits boundary tests.
  return conditional_access.routing_date() % 10000
end

function conditional_access.bicycle_is_forbidden(value, current_date)
  if not value or value == "" then
    return false, true
  end

  current_date = current_date or conditional_access.routing_month_day()
  local fully_supported = true
  local forbidden = false

  -- Intentionally support only recurring month/day ranges. Other valid OSM
  -- conditions are ignored until they can be evaluated completely and safely.
  for _, clause in ipairs(split_clauses(value)) do
    local start_month, start_day, end_month, end_day =
      string.match(clause, "^%s*no%s*@%s*%(%s*(%a%a%a)%s+(%d%d?)%s*%-%s*(%a%a%a)%s+(%d%d?)%s*%)%s*$")

    if start_month then
      local start_date = month_day(start_month, start_day)
      local end_date = month_day(end_month, end_day)
      if start_date and end_date and
          date_range_is_active(start_date, end_date, current_date) then
        forbidden = true
      elseif not start_date or not end_date then
        fully_supported = false
      end
    else
      fully_supported = false
    end
  end

  return forbidden, fully_supported
end

return conditional_access
