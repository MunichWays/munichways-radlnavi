import { fetchRoute, fetchRouteAnalysis } from "./routingRequests";

const route = {
  geometry: { type: "LineString", coordinates: [[11.59, 48.106], [11.593, 48.105]] },
  distance: 120.2, duration: 90, steps: [],
  analysis_legs: [{ nodes: [1, 2], distance: [120.2] }],
};
const response = (body: unknown, status = 200) => ({
  ok: status === 200, status, json: jest.fn().mockResolvedValue(body),
});
let originalFetch: typeof fetch;
beforeEach(() => {
  originalFetch = global.fetch;
  global.fetch = jest.fn();
});
afterEach(() => { global.fetch = originalFetch; });

test("unavailable direct service rejects before route state can be updated, then recovers", async () => {
  const unavailable = response({ detail: "Direct routing is not configured" }, 503);
  (fetch as jest.Mock).mockResolvedValueOnce(unavailable)
    .mockResolvedValueOnce(response({ ok: true, route }));
  const signal = new AbortController().signal;
  await expect(fetchRoute("/route?variant=direct", signal)).rejects.toThrow("HTTP 503");
  expect(unavailable.json).not.toHaveBeenCalled();
  await expect(fetchRoute("/route?variant=direct", signal)).resolves.toEqual(route);
});

test.each([{ ok: false }, {}, { ok: true, route: {} },
  { ok: true, route: { ...route, duration: null } },
  { ok: true, route: { ...route, geometry: { type: "LineString", coordinates: [] } } },
])("malformed 200 response cannot become a route: %j", async body => {
  (fetch as jest.Mock).mockResolvedValue(response(body));
  await expect(fetchRoute("/route", new AbortController().signal))
    .rejects.toThrow("Invalid routing response");
});

test("optional analysis failure does not mutate the usable route", async () => {
  (fetch as jest.Mock).mockResolvedValueOnce(response({ ok: true, route }))
    .mockResolvedValueOnce(response({ detail: "unavailable" }, 503));
  const signal = new AbortController().signal;
  const usable = await fetchRoute("/route", signal);
  await expect(fetchRouteAnalysis("/tag_distribution", usable, "direct", signal))
    .rejects.toThrow("HTTP 503");
  expect(usable).toEqual(route);
  expect(JSON.parse((fetch as jest.Mock).mock.calls[1][1].body)).toEqual({
    variant: "direct", legs: route.analysis_legs,
  });
  expect((fetch as jest.Mock).mock.calls[1][1].signal).toBe(signal);
});

test("cancellation reaches fetch and is not converted to a successful route", async () => {
  const error = new DOMException("Cancelled", "AbortError");
  (fetch as jest.Mock).mockRejectedValue(error);
  const controller = new AbortController();
  controller.abort();
  await expect(fetchRoute("/route", controller.signal)).rejects.toBe(error);
  expect(fetch).toHaveBeenCalledWith("/route", { signal: controller.signal });
});
