import { coordinateSuggestion } from "./coordinateSuggestion";

test.each([
  ["48.145548, 11.519868", "48.145548", "11.519868"],
  ["[48.145143, 11.526294]", "48.145143", "11.526294"],
  ["  [ -90, +180 ]  ", "-90", "180"],
  ["0, 0", "0", "0"],
])("accepts coordinate input %s without moving the point", (input, lat, lon) => {
  expect(coordinateSuggestion(input)).toEqual({
    display_name: `${lat}, ${lon}`, place_id: -1, lat, lon,
  });
});

test.each([
  "Marienplatz 1", "91, 11", "48, -181", "[48, 11", "48, 11]",
  "48, 11, 12", "NaN, 11", "48.1foo, 11", "", "1e2, 11",
])("does not offer invalid coordinates for %s", input => {
  expect(coordinateSuggestion(input)).toBeNull();
});
