/** Reject API errors before they can enter React route state. */
export async function fetchRoute(url: string, signal: AbortSignal) {
  const response = await fetch(url, { signal });
  if (!response.ok) {
    throw new Error(`Routing HTTP ${response.status}`);
  }
  const result = await response.json();
  const route = normalizeRouteResponse(result);
  if (!(result?.ok === true || result?.code === 'Ok') || !route ||
      route.geometry?.type !== "LineString" ||
      !Array.isArray(route.geometry.coordinates) ||
      route.geometry.coordinates.length < 2 ||
      !route.geometry.coordinates.every((p: unknown) => Array.isArray(p) &&
        p.length >= 2 && Number.isFinite(p[0]) && Number.isFinite(p[1])) ||
      !Array.isArray(route.steps) ||
      !Number.isFinite(route.distance) || route.distance < 0 ||
      !Number.isFinite(route.duration) || route.duration < 0) {
    throw new Error("Invalid routing response");
  }
  return route;
}

export function normalizeRouteResponse(result: any) {
  const raw = result?.routes?.[0];
  return raw ? { ...raw, response: result,
    // An intermediate arrival must not look like the final destination to the
    // existing web navigation. Keep every raw step in response for the app.
    steps: raw.legs?.flatMap((leg: any, i: number) => (leg.steps || []).filter((step: any) =>
      i === raw.legs.length - 1 || step.maneuver?.type !== 'arrive')),
    analysis_legs: raw.legs?.map((leg: any, i: number) => ({
      nodes: leg.annotation?.nodes, distance: leg.annotation?.distance,
      start: result.waypoints?.[i]?.location, end: result.waypoints?.[i + 1]?.location,
    })),
  } : result?.route;
}

export async function fetchRouteAnalysis(url: string, route: any,
    variant: string, signal: AbortSignal) {
  const response = await fetch(url, {
    signal,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(route.analysis_legs
      ? { variant, legs: route.analysis_legs }
      : { variant, node_ids: route.annotation?.nodes }),
  });
  if (!response.ok) throw new Error(`Analysis HTTP ${response.status}`);
  const result = await response.json();
  const tags = result?.tag_distribution;
  if (result?.ok !== true || !tags || !tags.lit || !tags.surface ||
      !tags["class:bicycle"]) throw new Error("Invalid analysis response");
  return result;
}
