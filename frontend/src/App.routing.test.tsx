import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

const mockHandlers: Record<string, Function> = {};
const mockMap = {
  on: (event: string, handler: Function) => { mockHandlers[event] = handler; },
  invalidateSize: jest.fn(), setBearing: jest.fn(),
};
jest.mock("leaflet.vectorgrid", () => {
  const L = require("leaflet");
  L.vectorGrid = { protobuf: () => ({ addTo: jest.fn(), removeFrom: jest.fn() }) };
  L.control.zoom = () => ({ addTo: jest.fn() });
  (globalThis as any).L = L;
  return {};
});
jest.mock("react-leaflet", () => {
  const React = require("react");
  const Empty = () => null;
  return {
    MapContainer: React.forwardRef(({ children }: any, ref: any) => {
      React.useImperativeHandle(ref, () => mockMap, []);
      return <div data-testid="map">{children}</div>;
    }),
    TileLayer: Empty, Marker: Empty, Popup: Empty, Polyline: Empty,
    Tooltip: Empty, Polygon: Empty,
  };
});
jest.mock("./RotatedMarker", () => () => null);
jest.mock("@mui/icons-material", () => Object.fromEntries(
  ["CenterFocusWeak", "Directions", "Download", "FitScreen", "GpsFixed",
    "GpsNotFixed", "GpsOff", "LegendToggle", "LocationSearching", "MenuOpen",
    "PlayArrow", "SwapVert"].map(name => [name, () => null])
));

// App reads the variant once per page load, as it does in the real test mode.
window.history.replaceState({}, "", "/?variant=direct");
const App = require("./App").default;

test("Route hierhin survives unavailable direct service and retry preserves route on analysis failure", async () => {
  const originalFetch = global.fetch;
  const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
  const log = jest.spyOn(console, "log").mockImplementation(() => {});
  let available = false;
  global.fetch = jest.fn(async (url: any) => {
    let body: any = {};
    let status = 200;
    if (String(url).includes("/route?")) {
      expect(String(url)).toContain("variant=direct");
      if (!available) {
        status = 503;
        body = { detail: "Direct routing is not configured" };
      } else {
        body = { ok: true, route: {
          geometry: { type: "LineString", coordinates: [[11.59, 48.106], [11.593, 48.105]] },
          distance: 120.2, duration: 90, steps: [],
          analysis_legs: [{ nodes: [1, 2], distance: [120.2] }],
        } };
      }
    } else if (String(url).includes("/tag_distribution")) {
      status = 503;
    } else if (url === "/region.json") {
      body = { features: [{ geometry: { coordinates: [[]] } }] };
    } else if (String(url).includes("nominatim")) {
      body = [];
    }
    return { ok: status === 200, status, json: async () => body } as Response;
  });
  try {
    const { unmount } = render(<App />);
    const open = (lat: number, lng: number) => act(() => {
      mockHandlers.contextmenu({
        originalEvent: { preventDefault() {}, clientX: 100, clientY: 100 },
        latlng: { lat, lng },
      });
    });
    await waitFor(() => expect(mockHandlers.contextmenu).toBeDefined());
    open(48.1064, 11.592893);
    fireEvent.click(screen.getByText("Route von hier"));
    open(48.105727, 11.593405);
    fireEvent.click(screen.getByText("Route hierhin"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Direkte Route ist derzeit nicht verfügbar");
    expect(screen.getByTestId("map")).toBeInTheDocument();
    expect(screen.queryByText("Navigation starten")).not.toBeInTheDocument();
    available = true;
    fireEvent.click(screen.getByText("Erneut versuchen"));
    expect(await screen.findByText("Navigation starten")).toBeEnabled();
    expect(await screen.findByText(/Die Route bleibt nutzbar/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    unmount();
  } finally {
    global.fetch = originalFetch;
    warn.mockRestore();
    log.mockRestore();
  }
});
