import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { TextEncoder, TextDecoder } from 'util';
import fixture from './fixtures/route-transfer.json';
import { transferGpx } from './routeTransfer';
Object.assign(globalThis, { TextEncoder, TextDecoder });

// Full MUI rendering plus debounced lookup/routing can exceed Jest's 5 s
// default on CI or while Android tooling is compiling on the same machine.
jest.setTimeout(15000);

const mockHandlers: Record<string, Function> = {};
const mockMap = {
  on: (event: string, handler: Function) => { mockHandlers[event] = handler; },
  invalidateSize: jest.fn(), setBearing: jest.fn(), fitBounds: jest.fn(),
};
jest.mock("leaflet.vectorgrid", () => {
  const L = require("leaflet");
  L.vectorGrid = { protobuf: () => ({ addTo: jest.fn(), removeFrom: jest.fn() }) };
  L.control.zoom = () => ({ addTo: jest.fn() });
  (globalThis as any).L = L;
  return {};
});

test('two intermediate stops use one ordered routing request and produce an exportable navigation snapshot', async () => {
  const original = global.fetch;
  const requests: string[] = [];
  global.fetch = jest.fn(async (url: any) => {
    requests.push(String(url));
    const body = String(url).includes('/route/v1/bike/') ? fixture.response :
      url === '/region.json' ? { features: [{ geometry: { coordinates: [[]] } }] } : {};
    return { ok: true, status: 200, json: async () => body } as Response;
  });
  const log = jest.spyOn(console, 'log').mockImplementation(() => {});
  const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
  try {
    const { unmount } = render(<App />);
    await waitFor(() => expect(mockHandlers.contextmenu).toBeDefined());
    const open = (lat: number, lng: number) => act(() => mockHandlers.contextmenu({ originalEvent: { preventDefault() {}, clientX: 100, clientY: 100 }, latlng: { lat, lng } }));
    open(48.15, 11.54); fireEvent.click(screen.getByText('Route von hier'));
    open(48.18, 11.57); fireEvent.click(screen.getByText('Route hierhin'));
    open(48.16, 11.55); fireEvent.click(screen.getByText('Zwischenziel setzen'));
    expect(screen.getByRole('combobox', { name: 'Zwischenziel 1' })).toHaveValue('[48.160000, 11.550000]');
    for (const [i, coords] of ['48.17, 11.56'].entries()) {
      fireEvent.click(screen.getByText('Zwischenziel hinzufügen'));
      fireEvent.change(screen.getByRole('combobox', { name: `Zwischenziel ${i + 2}` }), { target: { value: coords } });
      fireEvent.click(await screen.findByRole('option', { name: coords }));
    }
    await waitFor(() => expect(requests.some(url => url.includes('/route/v1/bike/11.54,48.15;11.55,48.16;11.56,48.17;11.57,48.18'))).toBe(true), { timeout: 5000 });
    await waitFor(() => expect(screen.getByText('GPX herunterladen')).toBeEnabled(), { timeout: 5000 });
    expect(screen.getByText('In App öffnen / teilen')).toBeEnabled();
    unmount();
  } finally { global.fetch = original; log.mockRestore(); warn.mockRestore(); }
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

test('GPX import explains original-route behavior only in the preview and keeps the exact route without recalculation', async () => {
  const original = global.fetch;
  const requests: string[] = [];
  global.fetch = jest.fn(async (url: any) => {
    requests.push(String(url));
    return { ok: true, status: 200, json: async () => url === '/region.json'
      ? { features: [{ geometry: { coordinates: [[]] } }] } : {} } as Response;
  });
  const log = jest.spyOn(console, 'log').mockImplementation(() => {});
  try {
    const { container, unmount } = render(<App />);
    const file = new File([], 'Tour.gpx');
    Object.assign(file, { text: async () => transferGpx(fixture as any) });
    fireEvent.change(container.querySelector('input[type=file]')!, { target: { files: [file] } });
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent('Importierte Originalstrecke: Änderungen an den Orten berechnen eine neue Route.');
    expect(dialog).toHaveTextContent('GPX herunterladen und in der MunichWays App importieren.');
    expect(dialog).not.toHaveTextContent('Danach diesen Link erneut öffnen');
    expect(dialog).not.toHaveTextContent('Übernehmen ersetzt die aktuelle Route');
    fireEvent.click(screen.getByRole('button', { name: 'Übernehmen' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(screen.queryByText(/Importierte Originalstrecke/)).not.toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Zwischenziel 1' })).toHaveValue(fixture.plan[1].name);
    expect(screen.getByRole('combobox', { name: 'Zwischenziel 2' })).toHaveValue(fixture.plan[2].name);
    expect(screen.getByRole('button', { name: 'GPX herunterladen' })).toBeEnabled();
    expect(requests.some(url => url.includes('/route/v1/'))).toBe(false);
    unmount();
  } finally { global.fetch = original; log.mockRestore(); }
});

test("coordinate selections retain exact start and destination alongside address suggestions", async () => {
  const originalFetch = global.fetch;
  const log = jest.spyOn(console, "log").mockImplementation(() => {});
  const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
  const requests: string[] = [];
  global.fetch = jest.fn(async (url: any) => {
    requests.push(String(url));
    let body: any = {};
    if (url === "/region.json") {
      body = { features: [{ geometry: { coordinates: [[]] } }] };
    } else if (String(url).includes("nominatim")) {
      body = [{ display_name: "Adresse in der Nähe", place_id: 42, lat: "48.14", lon: "11.52" }];
    }
    return { ok: true, status: 200, json: async () => body } as Response;
  });
  try {
    const { unmount } = render(<App />);
    const start = screen.getByRole("combobox", { name: "Startposition" });
    fireEvent.change(start, { target: { value: "48.145548, 11.519868" } });
    expect(await screen.findByRole("option", { name: "48.145548, 11.519868" })).toBeInTheDocument();
    expect(await screen.findByRole("option", { name: "Adresse in der Nähe" }, { timeout: 3000 })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("option", { name: "48.145548, 11.519868" }));
    const end = screen.getByRole("combobox", { name: "Ziel" });
    fireEvent.change(end, { target: { value: "[48.145143, 11.526294]" } });
    fireEvent.click(await screen.findByRole("option", { name: "48.145143, 11.526294" }));
    await waitFor(() => expect(requests.some(url => url.includes(
      "/route/v1/bike/11.519868,48.145548;11.526294,48.145143"
    ))).toBe(true), { timeout: 5000 });
    unmount();
  } finally {
    global.fetch = originalFetch;
    log.mockRestore();
    warn.mockRestore();
  }
});

test.each(['yes', 'home'])('address routing uses entrance=%s instead of the building centroid', async entranceType => {
  const houseNumber = entranceType === 'home' ? '16' : '19';
  const originalFetch = global.fetch;
  const log = jest.spyOn(console, 'log').mockImplementation(() => {});
  const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
  const requests: string[] = [];
  global.fetch = jest.fn(async (url: any) => {
    requests.push(String(url));
    let body: any = {};
    if (url === '/region.json') body = { features: [{ geometry: { coordinates: [[]] } }] };
    if (String(url).includes('nominatim')) {
      expect(String(url)).toContain('dedupe=0');
      expect(String(url)).toContain('entrances=1');
      const address = { road: 'Schloßschmidstraße', house_number: houseNumber, city: 'München' };
      body = [
        { place_id: 1, category: 'building', type: 'apartments', address: { ...address, house_number: entranceType === 'home' ? '16' : '19,21,23,25' },
          lat: '48.145', lon: '11.52', entrances: [{ type: entranceType, lat: '48.1467013', lon: '11.5169022', extratags: { 'addr:housenumber': houseNumber } }] },
        { place_id: 2, category: 'place', type: 'house', extratags: { entrance: entranceType }, address, lat: '48.1467013', lon: '11.5169022' },
      ];
    }
    return { ok: true, status: 200, json: async () => body } as Response;
  });
  try {
    const { unmount } = render(<App />);
    fireEvent.change(screen.getByRole('combobox', { name: 'Startposition' }), { target: { value: '48.146553, 11.519987' } });
    fireEvent.click(await screen.findByRole('option', { name: '48.146553, 11.519987' }));
    fireEvent.change(screen.getByRole('combobox', { name: 'Ziel' }), { target: { value: `Schloßschmidstraße ${houseNumber}` } });
    const options = await screen.findAllByRole('option', { name: `Schloßschmidstraße ${houseNumber}, München` }, { timeout: 3000 });
    fireEvent.click(options[0]);
    await waitFor(() => expect(requests.some(url => url.includes('/route/v1/bike/11.519987,48.146553;11.5169022,48.1467013'))).toBe(true), { timeout: 5000 });
    expect(requests.some(url => url.includes('/route/v1/bike/11.519987,48.146553;11.52,48.145'))).toBe(false);
    unmount();
  } finally {
    global.fetch = originalFetch;
    log.mockRestore();
    warn.mockRestore();
  }
});

test("Route hierhin survives unavailable direct service and retry preserves route on analysis failure", async () => {
  const originalFetch = global.fetch;
  const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
  const log = jest.spyOn(console, "log").mockImplementation(() => {});
  let available = false;
  global.fetch = jest.fn(async (url: any) => {
    let body: any = {};
    let status = 200;
    if (String(url).includes("/route/v1/bike/")) {
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
    expect(await screen.findByRole("alert", {}, { timeout: 5000 })).toHaveTextContent("Direkte Route ist derzeit nicht verfügbar");
    expect(screen.getByTestId("map")).toBeInTheDocument();
    expect(screen.queryByText("Navigation starten")).not.toBeInTheDocument();
    available = true;
    fireEvent.click(screen.getByText("Erneut versuchen"));
    expect(await screen.findByText("Navigation starten", {}, { timeout: 5000 })).toBeEnabled();
    expect(await screen.findByText(/Die Route bleibt nutzbar/, {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    unmount();
  } finally {
    global.fetch = originalFetch;
    warn.mockRestore();
    log.mockRestore();
  }
});
