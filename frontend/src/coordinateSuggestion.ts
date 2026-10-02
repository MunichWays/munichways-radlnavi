/** Coordinates are entered as latitude, longitude (also inside square brackets). */
export function coordinateSuggestion(value: string) {
  const input = value.trim();
  const pair = input.startsWith("[") && input.endsWith("]")
    ? input.slice(1, -1).trim() : input;
  const match = /^([+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*,\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+))$/.exec(pair);
  if (!match) return null;
  const lat = Number(match[1]);
  const lon = Number(match[2]);
  if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
  return {
    display_name: `${lat}, ${lon}`,
    place_id: -1,
    lat: String(lat),
    lon: String(lon),
  };
}
