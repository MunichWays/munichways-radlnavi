// @ts-nocheck
import React, { useState, useEffect, useCallback } from "react";
import "./App.css";
import { preferEntrances } from "./entrancePreference";
import { coordinateSuggestion } from "./coordinateSuggestion";
import { fetchRoute, fetchRouteAnalysis, normalizeRouteResponse } from "./routingRequests";
import { routeDisplaySections, withoutPushing } from "./routeDisplay";
import RouteInspector from './RouteInspector';
import {
  MapContainer as LeafletMap,
  TileLayer,
  Marker,
  Popup,
  Polyline,
  Tooltip as LeafletTooltip,
  Polygon
} from "react-leaflet";
import { LatLngBounds, LeafletEvent, LeafletMouseEvent, Map as LMap, Icon as LeafletIcon } from "leaflet";
import { throttle } from "lodash";
import { ToggleButtonGroup, ToggleButton, TextField, IconButton, LinearProgress, Button, createTheme, ThemeProvider, Autocomplete, Tooltip, Switch, FormControlLabel, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, Link, Typography, Drawer, Fab } from "@mui/material";
import { CenterFocusWeak, Directions, Download, FitScreen, GpsFixed, GpsNotFixed, GpsOff, LegendToggle, LocationSearching, MenuOpen, PlayArrow, SwapVert } from "@mui/icons-material";
import lineSlice from "@turf/line-slice";
import { point, lineString } from "@turf/helpers";
import length from "@turf/length";
import lineSliceAlong from "@turf/line-slice-along";
import RotatedMarker from './RotatedMarker';
import textInstructions from 'osrm-text-instructions';
import "leaflet.vectorgrid";

import RouteStops from './RouteStops';
import RouteShare from './RouteShare';
import StreetDetailsControl from './StreetDetailsDialog';
import { StreetFeature } from './streetDetails';
import { createTransfer, transferGpx, readTransferGpx, trackGpx, validateTransfer, gpxFilename, MAX_STOPS, MAX_TRANSFER_BYTES } from './routeTransfer';

const RADLNAVI_BLUE = "#00BCF2";
const ROUTE_BLUE = "#0057D9";

const RATING_COLORS = {
  black: "#000000",
  green: "#27F5A5",
  yellow: "#FFD000",
  red: "#F44336",
  grey: "#9C9D9F",
  brown: "#8D6E63",
};

const COMFORT_CATEGORIES = [
  { key: "black", label: "Sehr stressig", color: RATING_COLORS.black, classes: ["-3", "-2"] },
  { key: "red", label: "Stressig", color: RATING_COLORS.red, classes: ["-1"] },
  { key: "yellow", label: "Durchschnittlich", color: RATING_COLORS.yellow, classes: ["1"] },
  { key: "green", label: "Gemütlich", color: RATING_COLORS.green, classes: ["2", "3"] },
  { key: "unrated", label: "Nicht bewertet", color: RATING_COLORS.brown, classes: ["0", "unknown"] },
];

function comfortCategoryForClass(bicycleClass: string): string {
  return COMFORT_CATEGORIES.find(category => category.classes.includes(bicycleClass))?.key || "unrated";
}

const SOUTH_WEST = {
  lng: 8.5,
  lat: 47,
};

const NORTH_EAST = { lat: 51, lng: 14 };

const MAP_BOUNDS = new LatLngBounds(SOUTH_WEST, NORTH_EAST);

const RADLNAVI_THEME = createTheme({
  palette: {
    primary: {
      main: RADLNAVI_BLUE,
    },
  },
});

type LineGeo = Array<{ lat: number, lng: number }>;

interface NavigationStep {
  distance: number;
  maneuver: {
    type: "turn" | "arrive" | "end of road" | "continue",
    modifier: "left" | "slight left" | "straight" | "slight right" | "right",
  };
  geometry: LineGeo;
  description: string;
}

interface NominatimItem {
  display_name: string;
  place_id: number;
  lat: string;
  lon: string;
}

interface RouteMetadata {
  distance: number;
  duration: number;
}

interface VersionInfo {
  backend: string;
  backendCommit: string;
  routing: string;
  routingCommit: string;
  osrm: string;
}

interface ComfortInfo {
  index: number | null;
  coverage: number;
  sufficientCoverage: boolean;
  distribution: Record<string, number>;
}

function shortVersion(version: string): string {
  return /^[0-9a-f]{7,40}$/i.test(version) ? version.substring(0, 7) : version;
}

function VersionLink({label, version, commit}: {label: string, version: string, commit?: string}) {
  const displayVersion = /^\d+\.\d+\.\d+(?:[-+].+)?$/.test(version)
    ? `v${version}`
    : shortVersion(version);
  const text = `${label} ${displayVersion}`;
  const targetCommit = commit || (/^[0-9a-f]{7,40}$/i.test(version) ? version : "");
  if (!/^[0-9a-f]{7,40}$/i.test(targetCommit)) {
    return <span>{text}</span>;
  }
  return <Link
    href={`https://github.com/MunichWays/munichways-radlnavi/commit/${targetCommit}`}
    target="_blank"
    rel="noreferrer"
  >{text}</Link>;
}

interface QueryItem {
  distance: number;
  start: number;
  end: number;
  surface: string | undefined;
}

async function geocode(value: string): Promise<Array<NominatimItem>> {
  if (value.trim().length > 0) {
    const response = await fetch(
      `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(
        value
      )}&format=jsonv2&addressdetails=1&extratags=1&entrances=1&dedupe=0&viewbox=${SOUTH_WEST.lng},${SOUTH_WEST.lat},${NORTH_EAST.lng
      },${NORTH_EAST.lat}&bounded=1`
    );
    const places = await response.json();
    return preferEntrances(places, value);
  } else {
    return [];
  }
}

function displayDistance(distance: number): string {
  if (distance > 1000) {
    return `${Math.floor(distance / 1000)},${Math.round(
      (distance % 1000) / 10
    )} km`;
  } else {
    return `${Math.round(distance)} m`;
  }
}

function download(filename: string, xml: string): void {
  var element = document.createElement("a");
  element.setAttribute(
    "href",
    "data:application/gpx+xml;charset=utf-8," + encodeURIComponent(xml)
  );
  element.setAttribute("download", filename);

  element.style.display = "none";
  document.body.appendChild(element);

  element.click();

  document.body.removeChild(element);
}

function translateBicycleClass(bicycleClass: string): string {
  switch (bicycleClass) {
    case "-3":
      return "Unter allen Umständen vermeiden";
    case "-2":
      return "Nur wenn unbedingt nötig";
    case "-1":
      return "Wenn möglich vermeiden";
    case "1":
      return "In Ordnung";
    case "2":
      return "Sehr schöner Weg";
    case "3":
      return "Einen Umweg wert"
    default:
      return "Nicht bewertet"
  }
}

function translateSurface(surface: string): string {
  switch (surface) {
    case "paved":
      return "Befestigt";
    case "asphalt":
      return "Asphalt"
    case "concrete":
      return "Fest/Betoniert";
    case "concrete:lanes":
      return "Asphaltweg";
    case "concrete:plates":
      return "Asphaltplatten";
    case "paving_stones":
      return "Ebener Pflasterstein";
    case "sett":
      return "Pflasterstein";
    case "cobblestone":
      return "Rundlicher Pflasterstein";
    case "unhewn_cobblestone":
      return "Kopfsteinpflaster";
    case "unpaved":
      return "Uneben";
    case "compacted":
      return "Guter Waldweg";
    case "fine_gravel":
      return "Feiner Kies";
    case "pebblestone":
      return "Kies";
    case "gravel":
      return "Schotter";
    case "earth":
      return "Erde";
    case "dirt":
      return "Lockere Erde"
    case "ground":
      return "Erdboden";
    case "grass":
      return "Gras";
    case "grass_paver":
      return "Betonstein auf Gras";
    case "mud":
      return "Matsch";
    case "sand":
      return "Sand";
    case "woodchips":
      return "Holzschnitzel";
    default:
      return "Unbekannt";
  }
}

const BICYCLE_CLASSES_COLORS = new Map([
  ["-3", RATING_COLORS.black],
  ["-2", RATING_COLORS.black],
  ["-1", RATING_COLORS.red],
  ["0", RATING_COLORS.brown],
  ["1", RATING_COLORS.yellow],
  ["2", RATING_COLORS.green],
  ["3", RATING_COLORS.green],
  ["unknown", RATING_COLORS.brown],
])

const DASHED_BICYCLE_CLASSES = new Set(["-3", "-2", "-1"]);
const RATING_LEGEND = [
  { color: RATING_COLORS.green, label: "Gemütlich", dashed: false },
  { color: RATING_COLORS.yellow, label: "Durchschnittlich", dashed: false },
  { color: RATING_COLORS.red, label: "Stressig", dashed: true },
  { color: RATING_COLORS.black, label: "Sehr stressig", dashed: true },
];

function appRatingColor(color: string): string {
  switch (color.toLowerCase()) {
    case "black":
    case "schwarz": return RATING_COLORS.black;
    case "green":
    case "grün": return RATING_COLORS.green;
    case "yellow":
    case "gelb": return RATING_COLORS.yellow;
    case "red":
    case "rot": return RATING_COLORS.red;
    case "grey":
    case "gray":
    case "grau": return RATING_COLORS.grey;
    default: return color;
  }
}

function isStressfulRatingColor(color: string): boolean {
  const normalizedColor = appRatingColor(color).toUpperCase();
  return normalizedColor === RATING_COLORS.red || normalizedColor === RATING_COLORS.black;
}

const SURFACE_COLORS = new Map([
  ["asphalt", "#4682B4"],
  ["concrete", "#336187"],
  ["paved", "#385a75"],
  ["concrete:lanes", "#ADD8E6"],
  ["concrete:plates", "#B0C4DE"],
  ["paving_stones", "#C0C0C0"],
  ["sett", "#A9A9A9"],
  ["cobblestone", "#A9A9A9"],
  ["unhewn_cobblestone", "#808080"],
  ["unpaved", "#FFA07A"],
  ["compacted", "#006400"],
  ["fine_gravel", "#708090"],
  ["pebblestone", "#708090"],
  ["gravel", "#696969"],
  ["earth", "#CD853F"],
  ["dirt", "#CD853F"],
  ["ground", "#CD853F"],
  ["grass", "#228B22"],
  ["grass_paver", "#8FBC8F"],
  ["mud", "#BDB76B"],
  ["sand", "#F4A460"],
  ["woodchips", "#DEB887"],
]);

function translateLit(lit: string): string {
  if (lit === "no") {
    return "Nicht beleuchtet";
  } else if (lit === "yes") {
    return "Beleuchtet";
  } else {
    return "Unbekannt";
  }
}

const LIT_COLORS = new Map([
  ["yes", "yellow"],
  ["no", "black"],
  ["unknown", "grey"],
]);

const endMarkerIcon = new LeafletIcon({
  iconUrl: "marker-end.svg",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

const startMarkerIcon = new LeafletIcon({
  iconUrl: "marker-start.svg",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

const userMarkerIcon = new LeafletIcon({
  iconUrl: "marker-user.svg",
  iconSize: [48, 48],
  iconAnchor: [24, 24],
});

L.DomEvent.fakeStop = function () {
  return true;
}

let posChangeInterval = null;

const munichWaysLayer = L.vectorGrid.protobuf("/layers/munichways/{z}/{x}/{y}.pbf", {
  vectorTileLayerStyles: {
    munichways: (prop) => ({
      color: appRatingColor(prop.color),
      dashArray: isStressfulRatingColor(prop.color) ? "6 5" : undefined,
      weight: 1.5,
    })
  },
  interactive: false,
  rendererFactory: L.canvas.tile,
});

// Fixed for this page load: reloading with ?variant=direct starts a separate
// test session, so route and delayed comfort requests cannot switch variants.
const routingVariant = new URLSearchParams(window.location.search).get("variant") === "direct"
  ? "direct" : "standard";

function App() {
  const [startSuggestions, setStartSuggestions] = useState<
    Array<NominatimItem>
  >(new Array<NominatimItem>());
  const [endSuggestions, setEndSuggestions] = useState<Array<NominatimItem>>(
    new Array<NominatimItem>()
  );
  const [startValue, setStartValue] = useState("");
  const [endValue, setEndValue] = useState("");
  const [startPosition, setStartPosition] = useState<NominatimItem | null>(
    null
  );
  const [endPosition, setEndPosition] = useState<NominatimItem | null>(null);
  const [stops, setStops] = useState<any[]>([]);
  const [routeName, setRouteName] = useState('RadlNavi-Route');
  const [imported, setImported] = useState<any>(null);
  const [pendingImport, setPendingImport] = useState<any>(null);
  const [importError, setImportError] = useState('');
  const [route, setRoute] = useState<null | any>();
  const [showRouteInspector, setShowRouteInspector] = useState(false);
  const [inspectedStep, setInspectedStep] = useState<any>(null);
  const [routingError, setRoutingError] = useState<string | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [routingLoading, setRoutingLoading] = useState(false);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [surfacesOnRoute, setSurfacesOnRoute] = useState<null | Map<
    string,
    number
  >>(null);
  const [illuminatedOnRoute, setIlluminatedOnRoute] = useState<null | Map<
    string,
    number
  >>(null);
  const [illuminatedPaths, setIlluminatedPaths] = useState<null | Map<string, Array<Array<{ lat: number, lon: number }>>>>(null);
  const [surfacePaths, setSurfacePaths] = useState<null | Map<string, Array<Array<{ lat: number, lon: number }>>>>(null);
  const [comfortInfo, setComfortInfo] = useState<ComfortInfo | null>(null);
  const [bicycleClassesPaths, setBicycleClassesPaths] = useState<null | Map<string, Array<Array<{ lat: number, lon: number }>>>>(null);
  const [navigationPath, setNavigationPath] = useState<null | Array<{ lat: number, lng: number }> | null>(null);
  const [routeMetadata, setRouteMetadata] = useState<RouteMetadata | null>(
    null
  );
  const [contextMenuPosition, setContextMenuPosition] = useState<{
    left: number;
    top: number;
    lat: number;
    lng: number;
    zoom: number;
  } | null>(null);
  const [highlightedStreet, setHighlightedStreet] = useState<StreetFeature | null>(null);
  const [menuMinimized, setMenuMinimized] = useState<boolean>(false);
  const [hightlightLit, setHightlightLit] = useState<string | null>(null);
  const [hightlightSurface, setHightlightSurface] = useState<string | null>(null);
  const [highlightComfort, setHighlightComfort] = useState<string | null>(null);
  const [map, setMap] = useState<LMap | null>(null);
  const [showMunichways, setShowMunichways] = useState(true);
  const [showAbout, setShowAbout] = useState(false);
  const [showImpressum, setShowImpressum] = useState(false);
  const [showLegend, setShowLegend] = useState(false);
  const [isNavigating, setIsNavigating] = useState(false);
  const [geolocationWathId, setGeolocationWatchId] = useState<number | null>(null);
  const [userPosition, setUserPosition] = useState<null | { lat: number, lng: number, speed: number | null, heading: number | null }>(null);
  const [snappedUserPosition, setSnappedUserPosition] = useState<null | { lat: number, lng: number }>(null);
  const [wakeLock, setWakeLock] = useState<WakeLockSentinel | null>(null);
  const [nextNavigationStep, setNextNavigationStep] = useState<NavigationStep>(null);
  const [lineToRoute, setLineToRoute] = useState<LineGeo | null>(null);
  const [regionShape, setRegionShape] = useState<Polygon | null>(null);
  const [gpsMode, setGpsMode] = useState<"gps_off" | "gps_not_fixed" | "gps_fixed">("gps_off");
  const [versionInfo, setVersionInfo] = useState<VersionInfo | null>(null);
  const initialPositionRequested = React.useRef(false);

  const setCurrentPositionAsStart = useCallback((position: GeolocationPosition) => {
    const item = {
      display_name: "Aktuelle Position",
      place_id: 1,
      lat: position.coords.latitude.toString(),
      lon: position.coords.longitude.toString(),
    };
    setStartSuggestions([item]);
    setStartPosition(item);
  }, []);

  useEffect(() => {
    if (initialPositionRequested.current || !("geolocation" in navigator)) {
      return;
    }
    initialPositionRequested.current = true;
    navigator.geolocation.getCurrentPosition(setCurrentPositionAsStart, () => undefined, {
      enableHighAccuracy: true,
      maximumAge: 60000,
      timeout: 10000,
    });
  }, [setCurrentPositionAsStart]);

  useEffect(() => {
    fetch(`${process.env.REACT_APP_BACKEND_URL}/version`)
      .then(response => {
        if (!response.ok) {
          throw new Error(`Version request failed: ${response.status}`);
        }
        return response.json();
      })
      .then(setVersionInfo)
      .catch(error => console.warn("Could not load backend versions", error));
  }, []);

  const loadRegionShape = async () => {
    const regionGeoJson = await fetch("/region.json");
    const regionPoly = (await regionGeoJson.json()).features[0];
    console.log(regionPoly);
    const regionCoords = regionPoly.geometry.coordinates[0];
    console.log(regionCoords);
    regionCoords.unshift([
      0,
      90
    ],
      [
        180,
        90
      ],
      [
        180,
        -90
      ],
      [
        0,
        -90
      ],
      [
        -180,
        -90
      ],
      [
        -180,
        0
      ],
      [
        -180,
        90
      ],
      [
        0,
        90
      ]);
    const regionCoordsFixed = regionCoords.map(([x, y]) => [y, x]);
    console.log(regionCoordsFixed);
    setRegionShape(regionCoordsFixed);
  };

  useEffect(() => {
    if (!map) {
      return;
    }
    const resizeMap = () => map.invalidateSize({animate: false});
    requestAnimationFrame(resizeMap);
    const resizeTimer = window.setTimeout(resizeMap, 300);
    return () => window.clearTimeout(resizeTimer);
  }, [map, menuMinimized])

  useEffect(() => {
    loadRegionShape();
  }, []);

  useEffect(() => {
    if (map) {
      if (showMunichways) {
        munichWaysLayer.addTo(map);
      } else {
        munichWaysLayer.removeFrom(map);
      }
    }
  }, [map, showMunichways]);

  useEffect(() => {
    if (map) {
      L.control.zoom({
        position: 'topright'
      }).addTo(map);
    }
  }, [map]);

  useEffect(() => {
    let active = true;
    const exact = coordinateSuggestion(startValue);
    setStartSuggestions(exact ? [exact] : []);
    const timer = window.setTimeout(() => {
      geocode(startValue).then(items => {
        if (active) setStartSuggestions(exact ? [exact, ...items] : items);
      }).catch(error => console.warn("Could not load start suggestions", error));
    }, 1000);
    return () => { active = false; window.clearTimeout(timer); };
  }, [startValue]);

  useEffect(() => {
    let active = true;
    const exact = coordinateSuggestion(endValue);
    setEndSuggestions(exact ? [exact] : []);
    const timer = window.setTimeout(() => {
      geocode(endValue).then(items => {
        if (active) setEndSuggestions(exact ? [exact, ...items] : items);
      }).catch(error => console.warn("Could not load destination suggestions", error));
    }, 1000);
    return () => { active = false; window.clearTimeout(timer); };
  }, [endValue]);

  useEffect(() => {
    if (map) {
      if (gpsMode === "gps_fixed") {
        posChangeInterval = setInterval(() => {
          const targetHeading = 360 - userPosition?.heading;
          const currentHeading = map.getBearing();
          const headingDiff = ( targetHeading - currentHeading + 180 ) % 360 - 180;
          const headingDelta = headingDiff < -180 ? headingDiff + 360 : headingDiff;
          const headingStep = headingDelta / 10;
          if (Math.abs(headingDelta) > 1) {
            map.setBearing((map.getBearing() + headingStep) % 360);
          }

          const latDelta = map.getCenter().lat - userPosition?.lat;
          const lngDelta = map.getCenter().lng - userPosition?.lng;
          const latStep = latDelta / 10;
          const lngStep = lngDelta / 10;
          console.log(latDelta);
          if (Math.abs(latDelta) > 0.0001 || Math.abs(lngDelta) > 0.0001) {
            map.setView({lat: map.getCenter().lat - latStep, lng: map.getCenter().lng - lngStep});
          }
        }, 50);
      } else {
        clearInterval(posChangeInterval);
        posChangeInterval = null;
        map.setBearing(0);
      }
    }
    return () => clearInterval(posChangeInterval);
  }, [gpsMode, userPosition, map])

  useEffect(() => {
    if (map && gpsMode === "gps_fixed" && userPosition && isNavigating) {
      map.setZoom(20 - Math.min(5, (userPosition.speed || 0) / 2));
    }
  }, [map, gpsMode, isNavigating, userPosition]);

  useEffect(() => {
    if (isNavigating && route && userPosition && routeMetadata) {
      const line = lineString(route.geometry.coordinates);
      const navigationRoute = lineSlice(point([userPosition.lng, userPosition.lat]), point(route.geometry.coordinates[route.geometry.coordinates.length - 1]), line);
      setNavigationPath(navigationRoute.geometry.coordinates.map((pos) => ({ lat: pos[1], lng: pos[0] })));
      const distanceToTravel = length(navigationRoute, { units: "meters" });
      const distanceTravelled = routeMetadata.distance - distanceToTravel;

      // snap user position to route
      const fromUserToRoute = lineString([[userPosition.lng, userPosition.lat], navigationRoute.geometry.coordinates[0]]);
      const distanceToRoute = length(fromUserToRoute, { units: "meters" });
      if (distanceToRoute < 15) {
        setSnappedUserPosition({
          lat: navigationRoute.geometry.coordinates[0][1],
          lng: navigationRoute.geometry.coordinates[0][0],
        });
        setLineToRoute(null);
      } else {
        setSnappedUserPosition({
          ...userPosition,
        });
        setLineToRoute(fromUserToRoute.geometry?.coordinates?.map(coord => ({ lat: coord[1], lng: coord[0] })));
      }

      let upcomingStep = null;
      let travelled = distanceTravelled;
      let durationRemaining = 0;
      for (const index in route.steps) {
        if (travelled < 0) {
          upcomingStep = route.steps[index];
          const lastIndex = index >= 1 ? index - 1 : 0;
          durationRemaining = (Math.abs(travelled) / route.steps[lastIndex].distance) * route.steps[lastIndex].duration;
          for (let i = index; i < route.steps.length; i++) {
            durationRemaining += route.steps[i].duration;
          }
          break;
        }
        travelled -= route.steps[index].distance;
      }

      if (upcomingStep != null) {
        const nextStepDistanceFromStart = distanceTravelled + Math.abs(travelled);
        setNextNavigationStep({
          distance: Math.abs(travelled),
          remainingDistance: distanceToTravel,
          remainingDuration: durationRemaining,
          maneuver: upcomingStep?.maneuver,
          description: textInstructions("v5").compile("de", upcomingStep),
          geometry: lineSliceAlong(
            line,
            nextStepDistanceFromStart - 15,
            nextStepDistanceFromStart + 15,
            { units: "meters" },
          ).geometry?.coordinates?.map(coord => ({ lat: coord[1], lng: coord[0] })),
        });
      }
    } else {
      setSnappedUserPosition(null);
      setLineToRoute(null);
      setNextNavigationStep(null);
    }
  }, [userPosition, route, isNavigating, routeMetadata])

  const dragStartPosition = throttle((e: LeafletEvent) => {
    const pos = e.target?.getLatLng();
    if (pos) {
      routeFromHere(pos);
    }
  }, 500);

  const dragEndPosition = throttle((e: LeafletEvent) => {
    const pos = e.target?.getLatLng();
    if (pos) {
      routeToHere(pos);
    }
  }, 500);

  const analyzeRoute = async (route, signal: AbortSignal) => {
    setAnalysisLoading(true);
    try {
      const result = await fetchRouteAnalysis(
        `${process.env.REACT_APP_BACKEND_URL}/tag_distribution`, route, routingVariant, signal);
      if (signal.aborted) return;
      const { tag_distribution } = result;
      // Prepare all values before updating state so malformed optional data
      // cannot throw from a deferred React state updater and blank the page.
      const distances = (tag) => new Map(Object.entries(tag).map(([key, value]) => [key, value.distance]));
      const paths = (tag) => new Map(Object.entries(tag).map(([key, value]) =>
        [key, Object.values(value.ways).map(way => way.geometry.coordinates)]));
      const lit = distances(tag_distribution.lit);
      const litPaths = paths(tag_distribution.lit);
      const surfaces = distances(tag_distribution.surface);
      const surfacesPaths = paths(tag_distribution.surface);
      const bicyclePaths = paths(tag_distribution['class:bicycle']);
      setIlluminatedOnRoute(lit);
      setIlluminatedPaths(litPaths);
      setSurfacesOnRoute(surfaces);
      setSurfacePaths(surfacesPaths);
      setComfortInfo(result.comfort);
      setBicycleClassesPaths(bicyclePaths);
    } catch (error) {
      if (!signal.aborted) {
        console.warn("Route analysis unavailable", error);
        setAnalysisError("Radl-Komfort und Wegdetails sind derzeit nicht verfügbar. Die Route bleibt nutzbar.");
      }
    } finally {
      if (!signal.aborted) setAnalysisLoading(false);
    }
  };

  const calculateRoute = useCallback(async (startPosition, endPosition, stops, signal: AbortSignal) => {
    try {
      const nextRoute = await fetchRoute(
        `${process.env.REACT_APP_BACKEND_URL || ''}/route/v1/bike/${[startPosition, ...stops, endPosition].map(p => `${p.lon},${p.lat}`).join(';')}?variant=${routingVariant}&steps=true&overview=full&geometries=geojson&annotations=nodes,distance&alternatives=false&continue_straight=default`,
        signal);
      if (signal.aborted) return;
      setRoute(nextRoute);
      setRouteMetadata({ distance: nextRoute.distance, duration: nextRoute.duration });
      void analyzeRoute(nextRoute, signal);
    } catch (error) {
      if (!signal.aborted) {
        console.warn("Route unavailable", error);
        setRoutingError(routingVariant === "direct"
          ? "Direkte Route ist derzeit nicht verfügbar. Bitte prüfen, ob der Direkt-Dienst läuft, und erneut versuchen."
          : "Die Route konnte nicht berechnet werden. Bitte erneut versuchen.");
      }
    } finally {
      if (!signal.aborted) setRoutingLoading(false);
    }
  }, []);

  const transfer = React.useMemo(() => {
    if (!route?.response || !startPosition || !endPosition || stops.some(p => !p)) return null;
    try { return createTransfer(route, [startPosition, ...stops, endPosition], imported?.variant || routingVariant, routeName); }
    catch (_) { return null; }
  }, [route, startPosition, endPosition, stops, routeName, imported]);
  const exportGpx = () => {
    try {
      if (transfer) download(gpxFilename(transfer.name), transferGpx(transfer)); else if (imported?.version === 0) download(gpxFilename(routeName), trackGpx(routeName, route.geometry.coordinates, imported.plan));
    } catch (err) { setImportError(err.message); }
  };
  const applyImport = () => {
    const value = pendingImport;
    if (!value) return;
    const plan = value.plan.map((p, i) => ({ display_name: p.name || `Ort ${i + 1}`, place_id: -i - 1, lon: String(p.coordinates[0]), lat: String(p.coordinates[1]) }));
    setIsNavigating(false); setImported(value); setRouteName(value.name);
    setStartPosition(plan[0]); setStops(plan.slice(1, -1)); setEndPosition(plan[plan.length - 1]);
    setPendingImport(null); setImportError('');
  };
  useEffect(() => {
    const id = /^\/r\/([a-zA-Z0-9_-]{22,64})\/?$/.exec(window.location.pathname)?.[1];
    if (!id) return;
    const controller = new AbortController();
    fetch(`${process.env.REACT_APP_BACKEND_URL || ''}/shared_routes/${id}`, { signal: controller.signal })
      .then(async r => { if (!r.ok) throw new Error(r.status === 404 || r.status === 410 ? 'Dieser Link ist abgelaufen oder nicht mehr verfügbar.' : 'Route konnte nicht geladen werden. Bitte die Seite erneut öffnen.'); return r.json(); })
      .then(value => { if (!controller.signal.aborted) setPendingImport(validateTransfer(value)); })
      .catch(err => { if (!controller.signal.aborted) setImportError(err.message); });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    if (pendingImport && map) map.fitBounds(pendingImport.response.routes[0].geometry.coordinates.map(p => [p[1], p[0]]));
  }, [pendingImport, map]);

  const openContextMenu = useCallback((e: LeafletMouseEvent) => {
    e.originalEvent?.preventDefault();
    setContextMenuPosition({
      left: e.originalEvent?.clientX ?? document.documentElement.clientWidth / 2,
      top: e.originalEvent?.clientY ?? document.documentElement.clientHeight / 2,
      lat: e.latlng.lat,
      lng: e.latlng.lng,
      zoom: map.getZoom(),
    });
    console.log(
      "clicked on point",
      e.latlng,
      e.originalEvent.clientX,
      e.originalEvent.clientY
    );
    return false;
  }, [map]);

  const closeContextMenu = useCallback(() => {
    setContextMenuPosition(null);
  }, []);

  const startNavigation = useCallback(() => {
    setMenuMinimized(true);
    setIsNavigating(true);
    setGpsMode("gps_fixed");
  }, []);

  useEffect(() => {
    if ("geolocation" in navigator) {
      if (gpsMode === "gps_fixed" || gpsMode === "gps_not_fixed") {
        if (geolocationWathId == null) {
          const watchId = navigator.geolocation.watchPosition((position) => {
            setUserPosition({ lat: position.coords.latitude, lng: position.coords.longitude, speed: position.coords.speed, heading: position.coords.heading });
          }, (error) => {
            console.error(error);
          }, {
            enableHighAccuracy: true,
            maximumAge: 0,
          });
          setGeolocationWatchId(watchId);
        }
      } else {
        if (geolocationWathId) {
          navigator.geolocation.clearWatch(geolocationWathId);
          setGeolocationWatchId(null);
        }
      }
    }
  }, [gpsMode, geolocationWathId, route]);

  useEffect(() => {
    if ("wakeLock" in navigator) {
      if (isNavigating) {
        navigator.wakeLock.request().then(value => setWakeLock(value))
      } else {
        wakeLock?.release().then(() => setWakeLock(null));
      }
    }
  }, [isNavigating, wakeLock]);

  const routeFromHere = useCallback(
    (position: { lat: number; lng: number }) => {
      const item = {
        display_name: `[${position.lat.toPrecision(
          8
        )}, ${position.lng.toPrecision(8)}]`,
        place_id: 1,
        lat: position.lat.toString() || "0",
        lon: position.lng.toString() || "0",
      };
      setStartSuggestions([item]);
      setStartPosition(item);
      closeContextMenu();
    },
    []
  );

  const routeToHere = useCallback((position: { lat: number; lng: number }) => {
    const item = {
      display_name: `[${position.lat.toPrecision(
        8
      )}, ${position.lng.toPrecision(8)}]`,
      place_id: 2,
      lat: position.lat.toString() || "0",
      lon: position.lng.toString() || "0",
    };
    setEndSuggestions([item]);
    setEndPosition(item);
    closeContextMenu();
  }, []);

  const stopHere = (position: { lat: number; lng: number }) => {
    setStops(previous => previous.length >= MAX_STOPS ? previous : [...previous, {
      display_name: `[${position.lat.toPrecision(8)}, ${position.lng.toPrecision(8)}]`,
      place_id: -Date.now(), lat: String(position.lat), lon: String(position.lng),
    }]);
    closeContextMenu();
  };

  useEffect(() => {
    if (map != null) {
      const clearHighlight = () => {
        setHightlightSurface(null);
        setHightlightLit(null);
        setHighlightComfort(null);
      };
      map.on("contextmenu", openContextMenu);
      map.on("movestart", closeContextMenu);
      map.on("click", closeContextMenu);
      map.on("mouseover", clearHighlight);
      return () => {
        map.off("contextmenu", openContextMenu);
        map.off("movestart", closeContextMenu);
        map.off("click", closeContextMenu);
        map.off("mouseover", clearHighlight);
      };
    }
  }, [map, closeContextMenu, openContextMenu]);

  useEffect(() => {
    setNavigationPath(() => null);
    setNextNavigationStep(() => null);
    setUserPosition(() => null);
    setRoute(() => null);
    setIlluminatedOnRoute(() => null);
    setIlluminatedPaths(() => null);
    setSurfacesOnRoute(() => null);
    setSurfacePaths(() => null);
    setComfortInfo(() => null);
    setBicycleClassesPaths(() => null);
    setRouteMetadata(() => null);
    setRoutingError(null);
    setAnalysisError(null);
    setAnalysisLoading(false);
    setRoutingLoading(Boolean(startPosition && endPosition && stops.every(Boolean)));
    const controller = new AbortController();
    const plan = [startPosition, ...stops, endPosition];
    if (imported && plan.every(Boolean) && JSON.stringify(plan.map(p => [Number(p.lon), Number(p.lat)])) === JSON.stringify(imported.plan.map(p => p.coordinates))) {
      const restored = normalizeRouteResponse(imported.response);
      setRoute(restored); setRouteMetadata({ distance: restored.distance, duration: restored.duration });
      setRoutingLoading(false);
      return () => controller.abort();
    }
    if (imported) setImported(null);
    const timer = setTimeout(() => {
      if (startPosition && endPosition && stops.every(Boolean)) {
        void calculateRoute(startPosition, endPosition, stops, controller.signal);
      }
    }, 500);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [
    startPosition,
    endPosition,
    stops,
    imported,
  ]);

  let surfacesElement = null;
  let illuminatedElement = null;
  let comfortElement = null;

  if (startPosition != null && endPosition != null && comfortInfo != null && routeMetadata != null) {
    const categoryPercentages = COMFORT_CATEGORIES.map(category => ({
      ...category,
      percentage: comfortInfo.distribution[category.key] || 0,
    }));

    comfortElement = <div className="comfort-index">
      <div className="comfort-index-heading">
        <span>Radl-Komfort</span>
        <strong>{comfortInfo.sufficientCoverage && comfortInfo.index != null
          ? `${comfortInfo.index}/100`
          : "nicht ausreichend bewertet"}</strong>
      </div>
      <div className="comfort-bar" aria-label={`Radl-Komfort: ${comfortInfo.index == null ? "nicht ausreichend bewertet" : `${comfortInfo.index} von 100`}`}>
        {categoryPercentages
          .filter(category => category.percentage > 0)
          .map(category => <Tooltip
            key={category.key}
            arrow
            placement="top"
            title={`${category.label}: ${category.percentage} %`}
          >
            <div
              onTouchStart={() => setHighlightComfort(category.key)}
              onTouchEnd={() => setHighlightComfort(null)}
              onMouseOver={() => setHighlightComfort(category.key)}
              onMouseOut={() => setHighlightComfort(null)}
              style={{ background: category.color, flexGrow: category.percentage }}
            />
          </Tooltip>)}
      </div>
      <small>
        {comfortInfo.coverage} % der Route bewertet ·{" "}
        <Link
          href="https://www.munichways.de/berwertungskriterien-radwege/"
          target="_blank"
          rel="noreferrer"
        >Erläuterung</Link>
      </small>
    </div>;
  }


  if (startPosition != null && endPosition != null && surfacesOnRoute != null) {
    surfacesElement =
      <div style={{ display: 'flex', minHeight: '30px', border: '2px solid #666', borderRadius: 4 }}>{
        [...surfacesOnRoute.entries()]
          .sort((a, b) => a[1] - b[1])
          .map(([k, v]) => <div key={k} onTouchStart={() => setHightlightSurface(k)} onTouchEnd={() => setHightlightSurface(null)} onMouseOver={() => setHightlightSurface(k)} onMouseOut={() => setHightlightSurface(null)} id={k} style={{ background: SURFACE_COLORS.get(k) || 'gray', flexGrow: v / ([...surfacesOnRoute.values()].reduce((p, v) => p + v, 0)) * 100 }}></div>)
          .map((element) => element.key === hightlightSurface ? <Tooltip componentsProps={{
            tooltip: {
              sx: {
                backgroundColor: "black",
              }
            },
            arrow: {
              sx: {
                color: "black",
              }
            }
          }} arrow placement="top" title={translateSurface(hightlightSurface)}>{element}</Tooltip> : element)
          .reverse()
      }</div>;
  }

  if (startPosition != null && endPosition != null && illuminatedOnRoute != null) {
    illuminatedElement =
      <div style={{ display: 'flex', minHeight: '30px', marginTop: 0, border: '2px solid #666', borderRadius: 4 }}>{
        [...illuminatedOnRoute.entries()]
          .sort((a, b) => a[1] - b[1])
          .map(([k, v]) => <div key={k} onTouchStart={() => setHightlightLit(k)} onTouchEnd={() => setHightlightLit(null)} onMouseOver={() => setHightlightLit(k)} onMouseOut={() => setHightlightLit(null)} id={k} style={{ background: LIT_COLORS.get(k) || 'gray', flexGrow: v / ([...illuminatedOnRoute.values()].reduce((p, v) => p + v, 0)) * 100 }}></div>)
          .map((element) => element.key === hightlightLit ? <Tooltip componentsProps={{
            tooltip: {
              sx: {
                backgroundColor: "black",
              }
            },
            arrow: {
              sx: {
                color: "black",
              }
            }
          }} arrow placement="top" title={translateLit(hightlightLit)}>{element}</Tooltip> : element)
          .reverse()
      }</div>;
  }

  const routeMetaElement = routeMetadata ? (
    <div id="route-metadata">
      <div id="route-header" className="route-meta-heading">
        Berechnete Route
      </div>
      <div id="route-duration" className="route-meta">
        <div id="route-duration-key">Geschätzte Dauer</div>
        <div id="route-duration-value">
          {routeMetadata && imported?.version !== 0
            ? `${Math.round(routeMetadata.duration / 60)} Minuten`
            : "unbekannt"}
        </div>
      </div>
      <div id="route-distance" className="route-meta">
        <div id="route-distance-key">Gesamtdistanz</div>
        <div id="route-distance-value">
          {routeMetadata
            ? displayDistance(routeMetadata.distance)
            : "unbekannt"}
        </div>
      </div>
    </div>
  ) : null;

  const drawRoute = (route: any) => {
    const sections = routeDisplaySections(route);
    const ratings = bicycleClassesPaths == null ? null : [...bicycleClassesPaths.entries()]
      .map(([key, entry]) => [key, entry.flatMap(path => withoutPushing(path, sections))]);
    return <React.Fragment>
      {sections.map((section, i) => <Polyline key={`route-${i}-${section.pushing}`}
        dashArray={section.pushing ? "6 5" : undefined}
        weight={section.pushing || hightlightLit !== null || hightlightSurface !== null || highlightComfort !== null ? 3 : 8}
        positions={section.coordinates.map(([lng, lat]) => ({ lat, lng }))} color={ROUTE_BLUE} />)}
      {ratings == null ? sections.filter(section => !section.pushing).map((section, i) =>
        <Polyline key={`pending-${i}`} dashArray="2 4" color={ROUTE_BLUE} weight={2}
          positions={section.coordinates.map(([lng, lat]) => ({ lat, lng }))} />) : hightlightLit || hightlightSurface ? [] : ratings
        .filter(([key]) => highlightComfort == null || comfortCategoryForClass(key) === highlightComfort)
        .map(([key, entry]) => entry.map(
          (bicycleClassPath, i) =>
            <Polyline key={`${key}-${i}`} color={BICYCLE_CLASSES_COLORS.get(key) || RATING_COLORS.brown} dashArray={DASHED_BICYCLE_CLASSES.has(key) ? "6 5" : undefined} weight={3} positions={
              bicycleClassPath.map(
                (point) => ({ lat: point[1], lng: point[0] })
              )
            }>
              <LeafletTooltip interactive={true} sticky={true} content={translateBicycleClass(key)}>

              </LeafletTooltip>
            </Polyline>
        )
        )}
    </React.Fragment>
  };

  const drawIlluminated = () => {
    const sections = routeDisplaySections(route);
    const paths = illuminatedPaths == null ? [] : [...illuminatedPaths.entries()]
      .map(([key, entry]) => [key, entry.flatMap(path => withoutPushing(path, sections))]);
    return paths
      .filter(([key, _]) => key === hightlightLit)
      .map(([key, entry]) => entry.map(
        (litPath, i) =>
          <Polyline key={`${key}-${i}-backdrop`} color={ROUTE_BLUE} weight={8} positions={
            litPath.map(
              (point) => ({ lat: point[1], lng: point[0] })
            )
          }></Polyline>
      )
      ).concat(paths
        .filter(([key, _]) => key === hightlightLit)
        .map(([key, entry]) => entry.map(
          (litPath, i) =>
            <Polyline key={`${key}-${i}`} color={LIT_COLORS.get(key) || 'gray'} weight={4} positions={
              litPath.map(
                (point) => ({ lat: point[1], lng: point[0] })
              )
            }></Polyline>
        )
        ));
  };

  const drawSurfaces = () => {
    const sections = routeDisplaySections(route);
    const paths = surfacePaths == null ? [] : [...surfacePaths.entries()]
      .map(([key, entry]) => [key, entry.flatMap(path => withoutPushing(path, sections))]);
    return paths
      .filter(([key, _]) => key === hightlightSurface)
      .map(([key, entry]) => entry.map(
        (surfacePath, i) =>
          <Polyline key={`${key}-${i}-backdrop`} color={ROUTE_BLUE} weight={8} positions={
            surfacePath.map(
              (point) => ({ lat: point[1], lng: point[0] })
            )
          }></Polyline>
      )
      ).concat(paths
        .filter(([key, _]) => key === hightlightSurface)
        .map(([key, entry]) => entry.map(
          (surfacePath, i) =>
            <Polyline key={`${key}-${i}`} color={SURFACE_COLORS.get(key) || 'gray'} weight={4} positions={
              surfacePath.map(
                (point) => ({ lat: point[1], lng: point[0] })
              )
            }></Polyline>
        )
        ));


  };

  const goToMenu = useCallback(() => {
    setMenuMinimized(false);
    setIsNavigating(false);
  }, []);

  const showFullRoute = useCallback(() => {
    if (!map || !route) {
      return;
    }
    setMenuMinimized(true);
    window.setTimeout(() => {
      map.invalidateSize({animate: false});
      map.fitBounds(new LatLngBounds(route.geometry.coordinates.map((c: any) => {
        return [c[1], c[0]];
      })), {padding: [20, 20], maxZoom: 17, animate: false});
    }, 300);
  }, [map, route]);

  useEffect(() => {
    if (map != null) {
      window.document.onresize = () => {
        map.invalidateSize();
      }
    }
  }, [map]);

  return (
    <ThemeProvider theme={RADLNAVI_THEME}>
      <div className="App" style={{ display: 'flex' }} onResize={() => {
        if (map != null) {
          map.invalidateSize();
        }
      }}>
          <div
            id="menu"
            style={{
              display: contextMenuPosition ? 'flex' : 'none',
              left: Math.max(8, Math.min(contextMenuPosition?.left || 0, document.documentElement.clientWidth - 308)),
              top: Math.max(8, Math.min(contextMenuPosition?.top || 0, document.documentElement.clientHeight - 330)),
            }}
          >
            <Button
              color="primary"
              sx={{ textTransform: "none" }}
              onClick={() => routeFromHere(contextMenuPosition)}
            >
              Route von hier
            </Button>
            <Button
              color="primary"
              sx={{ textTransform: "none" }}
              onClick={() => routeToHere(contextMenuPosition)}
            >
              Route hierhin
            </Button>
            <Button color="primary" sx={{ textTransform: "none" }}
              disabled={stops.length >= MAX_STOPS}
              onClick={() => stopHere(contextMenuPosition)}>
              Zwischenziel setzen
            </Button>
            <StreetDetailsControl query={contextMenuPosition} onHighlight={setHighlightedStreet} />
          </div>

        <Tooltip title="Legende">
          <IconButton
            aria-label="Legende öffnen"
            onClick={() => setShowLegend(true)}
            sx={{
              position: "absolute",
              top: 82,
              right: 10,
              zIndex: 1000,
              backgroundColor: "white",
              boxShadow: 2,
              "&:hover": { backgroundColor: "#f5f5f5" },
            }}
          >
            <LegendToggle />
          </IconButton>
        </Tooltip>

        {menuMinimized ?
          <React.Fragment>
            <Fab color="primary" onClick={() => goToMenu()} style={{ position: "absolute", top: 15, left: 15, zIndex: 1 }}>
              <MenuOpen sx={{ transform: "scaleX(-1);" }} />
            </Fab>
            {isNavigating ?
              <Tooltip title="Gesamte Route anzeigen">
                <Fab color="primary" onClick={() => {
                  setIsNavigating(false);
                  showFullRoute();
                }} style={{ position: "absolute", top: 15, left: 85, zIndex: 1 }}>
                  <FitScreen />
                </Fab></Tooltip> :
              <Tooltip title="Starte interaktive Navigation">
                <Fab color="primary" onClick={() => setIsNavigating(true)} style={{ position: "absolute", top: 15, left: 85, zIndex: 1 }}>
                  <Directions />
                </Fab>
              </Tooltip>
            }
          </React.Fragment> : null}

        {menuMinimized && !isNavigating && route && comfortElement && surfacesElement && illuminatedElement ?
          <div style={{
            padding: 10,
            display: "flex",
            left: 15,
            bottom: 15,
            right: 15,
            minHeight: 150,
            position: "absolute",
            flexDirection: 'column',
            backgroundColor: "white",
            boxShadow: "0 0 5px 0 black",
            borderRadius: 10,
            zIndex: 1,
          }}>
            {comfortElement}
            <div style={{ height: 10 }}></div>
            {surfacesElement}
            <div style={{ height: 10 }}></div>
            {illuminatedElement}
          </div> : null}

        <Drawer sx={{".MuiDrawer-paper": {overflowY: "auto", overflowX: "hidden", display: "block", width: "min(360px, 100vw)"}, width: menuMinimized ? 0 : "min(360px, 100vw)", flexShrink: 0}}
                variant="persistent" anchor="left" open={!menuMinimized} onClose={() => setMenuMinimized(true)}
                onOpen={() => setMenuMinimized(false)}>

          <div className="planner-panel">
          <header className="planner-header">
            <div className="planner-brands">
              <img src="logo.svg" alt="RadlNavi Logo" />
              <img src="logo-munichways.svg" alt="MunichWays Logo" />
            </div>
            <IconButton aria-label="Menü ausblenden" size="small" onClick={() => setMenuMinimized(true)}>
              <MenuOpen />
            </IconButton>
          </header>
          <Typography className="planner-tagline">Fahrradnavigation für München und Umgebung</Typography>
          <div className="routing">
            {routingVariant === "direct" && (
              <Typography role="status" style={{padding: "8px 16px", fontWeight: "bold", background: "#e3f2fd"}}>
                Direkte Route (Testmodus)
              </Typography>
            )}
            <Button component="label" className="planner-import" size="small">GPX importieren
              <input hidden type="file" accept=".gpx,application/gpx+xml" onChange={async e => {
                const file = e.target.files?.[0]; e.target.value = '';
                if (!file) return;
                try { if (file.size > MAX_TRANSFER_BYTES) throw new Error('GPX-Datei ist zu groß (maximal 4 MB).'); setPendingImport(readTransferGpx(await file.text())); setImportError(''); }
                catch (err) { setImportError(err.message); }
              }} />
            </Button>
            {importError && <Typography role="alert" color="error" sx={{ m: 2 }}>{importError}</Typography>}
            <div className="planner-place">
              <Autocomplete
                  id="start"
                  filterOptions={(x) => x}
                  value={startPosition}
                  onInputChange={(_props, newValue: string, _reason) => {
                    console.log("set value", newValue);
                    setStartValue(newValue);
                  }}
                  clearOnBlur={false}
                  onChange={(e, newValue) => {
                    console.log("selected", newValue);
                    setStartPosition(newValue);
                    if (newValue == null) {
                      setRoute(null);
                      setRouteMetadata(null);
                    }
                  }}
                  options={startSuggestions}
                  getOptionLabel={(option: NominatimItem | null) =>
                      !option ? "" : option.display_name
                  }
                  size="small"
                  sx={{ flex: 1, minWidth: 0 }}
                  noOptionsText={"Für Vorschläge Adresse eingeben ..."}
                  renderInput={(params) => (
                      <TextField
                          {...params}
                          label="Startposition"
                          variant="outlined"
                          fullWidth
                      />
                  )}
              />
              <Tooltip title="Aktuelle Position ermitteln und als Start setzen" arrow>
                <IconButton color="primary"
                            onClick={() => navigator.geolocation.getCurrentPosition(setCurrentPositionAsStart)}><LocationSearching/></IconButton>
              </Tooltip>
            </div>
            <RouteStops stops={stops} onChange={setStops} />
            <div className="planner-place">
              <Autocomplete
                  id="end"
                  filterOptions={(x) => x}
                  value={endPosition}
                  clearOnBlur={false}
                  onInputChange={(_props, newValue: string, _reason) => {
                    console.log("set value", newValue);
                    setEndValue(newValue);
                  }}
                  onChange={(e, newValue) => {
                    console.log("selected", newValue);
                    setEndPosition(newValue);
                    if (newValue == null) {
                      setRoute(null);
                      setRouteMetadata(null);
                    }
                  }}
                  options={endSuggestions}
                  getOptionLabel={(option: NominatimItem | null) =>
                      !option ? "" : option.display_name
                  }
                  size="small"
                  sx={{ flex: 1, minWidth: 0 }}
                  noOptionsText={"Für Vorschläge Adresse eingeben ..."}
                  renderInput={(params) => (
                      <TextField
                          {...params}
                          label="Ziel"
                          variant="outlined"
                          fullWidth
                      />
                  )}
              />
              <Tooltip title="Route umkehren" placement="top" arrow>
                <IconButton disabled={startPosition == null || endPosition == null} color="primary" onClick={() => {
                  const tmp = startPosition;
                  setStartPosition(endPosition);
                  setEndPosition(tmp);
                  setStops([...stops].reverse());
                }}><SwapVert></SwapVert></IconButton>
              </Tooltip>
            </div>
            {routingError && <Typography role="alert" color="error" sx={{m: 2}}>{routingError}</Typography>}
            {analysisError && <Typography role="status" sx={{m: 2}}>{analysisError}</Typography>}
            {routingError && <Button onClick={() => setEndPosition({...endPosition})}>Erneut versuchen</Button>}
            <TextField label="Routenname" value={routeName} onChange={e => setRouteName(e.target.value)} inputProps={{ maxLength: 200 }} size="small" />
            {routeMetaElement}
            {route && map ? <Button variant="contained" startIcon={<CenterFocusWeak/>}
                onClick={showFullRoute}>Route anzeigen</Button> : null}
            {(routingLoading || analysisLoading) ? <LinearProgress sx={{height: 4, borderRadius: 4}}/> : null}
            {comfortElement}
            <div className="planner-actions">
              {route != null ? <Button variant="outlined" onClick={exportGpx}
                  disabled={!transfer && imported?.version !== 0} startIcon={<Download/>}>
                GPX herunterladen
              </Button> : null}
              <RouteShare transfer={transfer} />
            </div>
            <details className="planner-more">
              <summary>Mehr</summary>
              <div className="planner-more-content">
                <Button variant="outlined" onClick={() => setShowRouteInspector(true)}>Hinweise prüfen</Button>
                <Button variant="outlined" onClick={() => {
                  const center = map?.getCenter();
                  if (center) setContextMenuPosition({ left: window.innerWidth / 2, top: window.innerHeight / 2,
                    lat: center.lat, lng: center.lng, zoom: map.getZoom() });
                }}>Streckendetails an Kartenmitte</Button>
                {route != null && imported?.version !== 0 ? <Button variant="outlined"
                    onClick={startNavigation} startIcon={<PlayArrow/>}>Navigation starten</Button> : null}
                {surfacesElement && <section aria-label="Untergrund">
                  <Typography variant="subtitle2">Untergrund</Typography>
                  {surfacesElement}
                </section>}
                {illuminatedElement && <section aria-label="Beleuchtung">
                  <Typography variant="subtitle2">Beleuchtung</Typography>
                  {illuminatedElement}
                </section>}
                <FormControlLabel sx={{m: 0}}
                    control={<Switch size="small" checked={showMunichways} onChange={(_, checked) => setShowMunichways(checked)}/>}
                    label="Bewertungen"/>
                <Link component="button" underline="hover" onClick={() => setShowAbout(true)}>
                  Über RadlNavi
                </Link>
                <Link component="button" underline="hover" onClick={() => setShowImpressum(true)}>
                  Impressum und Datenschutzerklärung
                </Link>
                <div className="planner-versions">
                  <strong>Versionen: </strong>
                  <VersionLink label="FE" version={process.env.REACT_APP_VERSION || "local"}
                               commit={process.env.REACT_APP_COMMIT}/>
                  {versionInfo == null ? <span> · BE/Routing werden geladen</span> : <>
                    <span> · </span><VersionLink label="BE" version={versionInfo.backend} commit={versionInfo.backendCommit}/>
                    <span> · </span><VersionLink label="Routing" version={versionInfo.routing} commit={versionInfo.routingCommit}/>
                    <span> · OSRM {versionInfo.osrm}</span>
                  </>}
                </div>
              </div>
            </details>
          </div>
          </div>
        </Drawer>

        <div style={{
          position: "absolute",
          right: 60,
          top: 10,
          zIndex: 1000,
          background: "white",
        }}>
          <ToggleButtonGroup
            color="primary"
            value={gpsMode}
            exclusive
            onChange={(e, newGpsMode) => {
              setGpsMode(newGpsMode);
          }}
          >
            <ToggleButton size="small" value="gps_off"><Tooltip title="Kein GPS auf Karte anzeigen"><GpsOff /></Tooltip></ToggleButton>
            <ToggleButton size="small" value="gps_not_fixed"><Tooltip title="GPS auf Karte anzeigen"><GpsNotFixed /></Tooltip></ToggleButton>
            <ToggleButton size="small" value="gps_fixed"><Tooltip title="GPS auf Karte anzeigen und verfolgen"><GpsFixed /></Tooltip></ToggleButton>
          </ToggleButtonGroup>
        </div>

        {isNavigating && nextNavigationStep ? <div style={{
          position: "absolute",
          left: 10,
          right: 10,
          bottom: 20,
          zIndex: 1000,
          background: "#00BCF2",
          padding: 10,
          borderRadius: 10,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "stretch",
        }}>

        {nextNavigationStep.maneuver.type != "arrive" ?
          <div style={{
            position: "absolute",
            top: 10,
            zIndex: 1100,
            background: "#000",
            padding: 10,
            borderRadius: 10,
            transform: "translate(-50%,-100%)",
            width: "max-content",
            left: "50%",
            color: "white",
            textAlign: "center",
          }}>
              Ankunft in <b>etwa {Math.ceil(nextNavigationStep.remainingDuration / 60)} min</b> ({Math.round(nextNavigationStep.remainingDistance / 100) / 10} km)
          </div> : null}
      
          {nextNavigationStep.maneuver.type != "arrive" && nextNavigationStep.maneuver?.modifier == null ? <div style={{ flexGrow: 1 }}></div> :
            <div style={{
              backgroundImage: `url(./${nextNavigationStep.maneuver?.type == "arrive" ? "arrive" : "maneuver_" + nextNavigationStep.maneuver.modifier.replaceAll(" ", "_")}.svg)`,
              backgroundRepeat: "no-repeat",
              flexGrow: 1,
              minWidth: 70,
              backgroundPositionY: "center",
            }}>
            </div>}

          <div style={{ textAlign: "left", flexGrow: 1 }}>
            <span style={{ fontSize: "2rem" }}>{Math.round(nextNavigationStep.distance / 10) * 10}m</span><br />
            <i>{nextNavigationStep.description}</i>
          </div>
        </div> : null}

        <LeafletMap
          className="map"
          center={[48.134991, 11.584225]}
          zoom={14}
          zoomSnap={0.5}
          zoomDelta={0.5}
          zoomAnimation={true}
          zoomControl={false}
          maxBounds={MAP_BOUNDS}
          ref={setMap}
          rotate={true}
          tapHold={true}
        >
          <TileLayer
            attribution='&amp;copy <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {inspectedStep?.maneuver?.location && <Marker icon={endMarkerIcon}
            position={[inspectedStep.maneuver.location[1], inspectedStep.maneuver.location[0]]}>
            <Popup>Prüfhinweis: {inspectedStep.maneuver.type} / {inspectedStep.maneuver.modifier || '—'}
              <button onClick={() => { setInspectedStep(null); setShowRouteInspector(true); }}>Zur Prüfliste</button>
            </Popup>
          </Marker>}
          {inspectedStep?.geometry?.type === 'LineString' && <Polyline color="#d65a00" weight={7}
            positions={inspectedStep.geometry.coordinates.map(([lon, lat]) => [lat, lon])} />}
          {startPosition != null ? (
            <Marker
              icon={startMarkerIcon}
              draggable={true}
              eventHandlers={{
                drag: (e) => dragStartPosition(e),
              }}
              position={[
                parseFloat(startPosition.lat),
                parseFloat(startPosition.lon),
              ]}
            >
              <Popup>{startPosition.display_name}</Popup>
            </Marker>
          ) : null}
          {endPosition != null ? (
            <Marker
              icon={endMarkerIcon}
              draggable={true}
              eventHandlers={{
                drag: (e) => dragEndPosition(e),
              }}
              position={[
                parseFloat(endPosition.lat),
                parseFloat(endPosition.lon),
              ]}
            >
              <Popup>{endPosition.display_name}</Popup>
            </Marker>
          ) : null}
          {userPosition != null && gpsMode === "gps_fixed" ? (
            <Marker
            icon={userMarkerIcon}
            draggable={false}
            position={[
              snappedUserPosition?.lat || userPosition.lat,
              snappedUserPosition?.lng || userPosition.lng,
            ]}
          ></Marker>
          ) : userPosition != null && gpsMode === "gps_not_fixed" ? <RotatedMarker
          icon={userMarkerIcon}
          draggable={false}
          position={[
            snappedUserPosition?.lat || userPosition.lat,
            snappedUserPosition?.lng || userPosition.lng,
          ]}
          rotationAngle={userPosition.heading || 0}
          rotationOrigin={"center center"}
        ></RotatedMarker> : null}
          {stops.map((p, i) => p && <Marker key={`stop-${i}`} draggable position={[Number(p.lat), Number(p.lon)]}
            eventHandlers={{ dragend: e => { const pos = e.target.getLatLng(); setStops(stops.map((s, j) => j === i ? { ...s, lat: String(pos.lat), lon: String(pos.lng) } : s)); } }}><Popup>Zwischenziel {i + 1}: {p.display_name}</Popup></Marker>)}
          {pendingImport && <Polyline color="#0057D9" dashArray="8 6" positions={pendingImport.response.routes[0].geometry.coordinates.map(p => [p[1], p[0]])} />}
          {route != null && startPosition != null && endPosition != null
            ? drawRoute(route)
            : null}
          {illuminatedPaths != null && startPosition != null && endPosition != null && hightlightLit !== null ? drawIlluminated() : null}
          {surfacePaths != null && startPosition != null && endPosition != null && hightlightSurface !== null ? drawSurfaces() : null}
          {!isNavigating || navigationPath == null || route == null || lineToRoute == null ? null :
            <Polyline color="red" dashArray="7 7" weight={4} positions={
              lineToRoute
            }></Polyline>
          }
          {regionShape == null ? null : <Polygon fillColor="black" weight={0} fillOpacity={0.5} positions={regionShape}></Polygon>}
          {highlightedStreet && <Polyline positions={highlightedStreet.geometry.coordinates.map(([lng, lat]) => [lat, lng])}
            pathOptions={{ color: '#8E24AA', weight: 9, opacity: 0.85 }} interactive={false} />}
        </LeafletMap>
      </div>

      {navigationPath == null || route == null || lineToRoute == null || !isNavigating ? null :
        <Button
          variant="contained"
          color="warning"
          style={{
            position: "fixed",
            top: "20vh",
            left: "50%",
            transform: "translateX(-50%)"
          }} onClick={() => routeFromHere(lineToRoute[0])}>Route neu berechnen</Button>
      }

      <Dialog open={Boolean(pendingImport)} onClose={() => setPendingImport(null)}>
        <DialogTitle>Route übernehmen?</DialogTitle>
        <DialogContent>{pendingImport && <>
          <p>{pendingImport.name} · {(pendingImport.response.routes[0].distance / 1000).toFixed(1)} km · {pendingImport.plan.length - 2} {pendingImport.plan.length === 3 ? 'Zwischenziel' : 'Zwischenziele'}</p>
          <p>Die gestrichelte Linie zeigt die Originalstrecke. {pendingImport.version === 1 ? 'Die Route enthält Abbiegehinweise.' : 'Track ohne Abbiegehinweise und Fahrzeit.'}</p>
          <p>Importierte Originalstrecke: Änderungen an den Orten berechnen eine neue Route.</p>
          <p>GPX herunterladen und in der MunichWays App importieren.</p>
          <p>MunichWays installieren: <a href="https://play.google.com/store/apps/details?id=com.munichways.app">Android</a> · <a href="https://apps.apple.com/app/id1534934984">iPhone</a>.</p>
          <Button onClick={() => download(gpxFilename(pendingImport.name), pendingImport.version === 1 ? transferGpx(pendingImport) : trackGpx(pendingImport.name, pendingImport.response.routes[0].geometry.coordinates, pendingImport.plan))}>GPX herunterladen</Button>
        </>}</DialogContent>
        <DialogActions><Button onClick={() => setPendingImport(null)}>Abbrechen</Button><Button onClick={applyImport}>Übernehmen</Button></DialogActions>
      </Dialog>
      <RouteInspector open={showRouteInspector} onClose={() => setShowRouteInspector(false)}
        startPosition={startPosition} endPosition={endPosition}
        route={route} variant={routingVariant} onMap={step => {
          setInspectedStep(step);
          setGpsMode('gps_off');
          map?.setView([step.maneuver.location[1], step.maneuver.location[0]], 19);
        }} />
      <Dialog open={showAbout}>
        <DialogTitle>Über RadlNavi</DialogTitle>
        <DialogContent>
          <DialogContentText>
            RadlNavi findet angenehmere Fahrradverbindungen – möglichst über komfortable Wege, ruhigere Straßen und mit weniger schwierigen Querungen.<br /><br />
            Die farbigen Linien zeigen das von Radfahrer*innen gemeinsam bewertete Radnetz: von Grün für angenehm bis Schwarz für besonders stressig.<br /><br />
            <a href="https://www.munichways.de/radlvorrangnetz/" target="_blank" rel="noreferrer">Mehr über das RadlVorrang-Netz und die Bewertung erfahren</a>
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowAbout(false)}>Schließen</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={showLegend} onClose={() => setShowLegend(false)}>
        <DialogTitle>Bewertungen</DialogTitle>
        <DialogContent>
          {RATING_LEGEND.map(({color, label, dashed}) => (
            <div key={label} style={{display: "flex", alignItems: "center", gap: 12, margin: "12px 0"}}>
              <span style={{
                display: "inline-block",
                width: 54,
                height: 4,
                background: dashed
                  ? `repeating-linear-gradient(to right, ${color} 0 8px, transparent 8px 13px)`
                  : color,
              }} />
              <Typography>{label}</Typography>
            </div>
          ))}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowLegend(false)}>Schließen</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={showImpressum}>
        <DialogTitle>Impressum und Datenschutzerklärung</DialogTitle>
        <DialogContent>
          <DialogContentText>
            RadlNavi wird von MunichWays angeboten und weiterentwickelt.<br /><br />
            Florian Schnell hat das ursprüngliche <a href="https://www.radlnavi.de"
              target="_blank" rel="noreferrer">RadlNavi</a> entwickelt.<br /><br />
            Alle Angaben zum Datenschutz und zur verantwortlichen Stelle stehen in der <a
              href="https://www.munichways.de/datenschutzerklaerung-app/"
              target="_blank" rel="noreferrer">Datenschutzerklärung für die MunichWays App</a>.<br /><br />
            Ergänzend gelten die <a href="https://www.munichways.de/nutzungbedingungen-app/"
              target="_blank" rel="noreferrer">Nutzungsbedingungen für die MunichWays App</a>.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowImpressum(false)}>Schließen</Button>
        </DialogActions>
      </Dialog>
    </ThemeProvider >
  );
}

export default App;
