import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import RouteInspector, { listSteps } from './RouteInspector';
import wilram from './testFixtures/wilram-sequence.json';
import { appGuidancePreview } from './appGuidancePreview';

const step = (type: string, modifier: string | undefined, distance: number) => ({
  maneuver: { type, modifier, location: [11.52138, 48.145394], bearing_after: 90, bearing_before: 0 },
  distance, duration: 3, name: 'Birketweg', mode: 'cycling',
});
const steps = [step('depart', undefined, 47.2), step('continue', 'left', 12.2),
  step('turn', 'right', 87.7), step('arrive', undefined, 0)];

test('preserves close opposite maneuvers and accumulates distances across legs without mutation', () => {
  const route = { legs: [{ steps }, { steps: [step('depart', undefined, 5), step('arrive', undefined, 0)] }] };
  const before = JSON.stringify(route);
  const rows = listSteps(route);
  expect(rows).toHaveLength(6);
  expect(rows[1].at).toBe(47.2);
  expect(rows[2].at).toBeCloseTo(59.4);
  expect(rows[4].at).toBeCloseTo(147.1);
  expect(rows[5].at).toBeCloseTo(152.1);
  expect(rows[1].instruction).toMatch(/links/i);
  expect(rows[2].instruction).toMatch(/rechts/i);
  expect(rows[4].legIndex).toBe(1);
  expect(JSON.stringify(route)).toBe(before);
});

test('detects way changes for the app preview without altering raw instructions', () => {
  const route = { legs: [{ steps: [
    { ...step('depart', undefined, 60), intersections: [{ classes: ['road'] }] },
    { ...step('turn', 'right', 60), name: 'Bodenstedtstraße',
      intersections: [{ classes: ['cycleway'] }] },
    { ...step('turn', 'left', 30), intersections: [{ classes: ['road'] }] },
    { ...step('turn', 'right', 20), intersections: [{ classes: [] }] },
    { ...step('turn', 'left', 10), intersections: [{ classes: ['cycleway'] }] },
  ] }] };
  const before = JSON.stringify(route);
  const rows = listSteps(route);
  expect(rows[0].detectedWayType).toBeNull();
  expect(rows[1].instruction).toContain('Bodenstedtstraße');
  expect(rows[1].instruction).not.toContain('auf Radweg');
  expect(rows[2].detectedWayType).toBe('road');
  expect(rows[3].detectedWayType).toBeNull();
  expect(rows[4].detectedWayType).toBeNull();
  expect(JSON.stringify(route)).toBe(before);
});

test('shows paired raw/app instructions, quiet steps and alternative Wilram guidance', () => {
  const onMap = jest.fn();
  const route = wilram.routes[0];
  const before = JSON.stringify(route);
  render(<RouteInspector open onClose={jest.fn()} onMap={onMap} route={route} variant="discovery" />);
  expect(screen.queryByRole('option', { name: 'Automatisch aus Routendaten' })).not.toBeInTheDocument();
  expect(screen.getByText('Variante: Entdeckertour')).toBeInTheDocument();
  expect(screen.getAllByText(/^RadlNavi:/).length).toBeGreaterThan(1);
  expect(screen.getAllByText(/Keine Einzelansage/).length).toBeGreaterThan(0);
  const checkpoint = screen.getByText(/Alternative Anfahrt: Hier geradeaus/);
  const item = checkpoint.closest('li')!;
  const mapButton = Array.from(item.querySelectorAll('button')).find(b => b.textContent?.includes('auf Karte'))!;
  fireEvent.click(mapButton);
  expect(onMap.mock.calls[0][0].maneuver.location).toEqual(
    (route.guidance.junctions[0] as any).sequence.checkpoints[0].anchor.location);
  expect(JSON.stringify(route)).toBe(before);
});

test('uses the map route immediately and passes its exact step to the map', () => {
  const onMap = jest.fn();
  const onClose = jest.fn();
  render(<RouteInspector open onClose={onClose} onMap={onMap}
    route={{ distance: 147.2, legs: [{ steps }] }} variant="standard" />);
  expect(screen.getByText('continue / left')).toBeInTheDocument();
  expect(screen.getByText('turn / right')).toBeInTheDocument();
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  expect(screen.queryByText('Aktuelle Kartenroute \u00fcbernehmen')).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Kreuzungs\u00fcbersicht' })).toHaveAttribute(
    'href', '/docs/large-junction-analysis/kreuzungspruefung/index.html');
  fireEvent.click(screen.getByText('Hinweis 2 auf Karte'));
  expect(onMap).toHaveBeenCalledWith(steps[1]);
  expect(onClose).not.toHaveBeenCalled();
  expect(screen.getByRole('dialog')).toHaveAttribute('aria-modal', 'false');
});

test('reads instructions in order and stops the old sequence when the map route changes', () => {
  const originalSpeech = window.speechSynthesis;
  const originalUtterance = window.SpeechSynthesisUtterance;
  const spoken: any[] = [];
  Object.defineProperty(window, 'speechSynthesis', { configurable: true, writable: true, value: {
    cancel: jest.fn(), speak: (utterance: any) => spoken.push(utterance),
  } });
  Object.defineProperty(window, 'SpeechSynthesisUtterance', { configurable: true, writable: true,
    value: class { text: string; constructor(text: string) { this.text = text; } } });
  const props = { onClose: jest.fn(), onMap: jest.fn(), route: { steps, distance: 147.2 }, variant: 'standard' };
  try {
    const view = render(<RouteInspector {...props} open />);
      fireEvent.click(screen.getByText('RadlNavi: Alle Hinweise vorlesen'));
    expect(spoken).toHaveLength(1);
    act(() => spoken[0].onend());
    expect(spoken[1].text).toMatch(/links/i);
    act(() => spoken[1].onend());
    expect(spoken[2].text).toMatch(/rechts/i);
    view.rerender(<RouteInspector {...props} open route={{ ...props.route, distance: 200 }} />);
    act(() => spoken[2].onend());
    expect(spoken).toHaveLength(3);
    expect(window.speechSynthesis.cancel).toHaveBeenCalled();
    view.unmount();
  } finally {
    if (originalSpeech === undefined) delete (window as any).speechSynthesis;
    else Object.defineProperty(window, 'speechSynthesis', { configurable: true, writable: true, value: originalSpeech });
    if (originalUtterance === undefined) delete (window as any).SpeechSynthesisUtterance;
    else Object.defineProperty(window, 'SpeechSynthesisUtterance', { configurable: true, writable: true, value: originalUtterance });
  }
});

test('app playback reads macro and checkpoint speech, skipping quiet raw steps', () => {
  const originalSpeech = window.speechSynthesis;
  const originalUtterance = window.SpeechSynthesisUtterance;
  const spoken: any[] = [];
  Object.defineProperty(window, 'speechSynthesis', { configurable: true, writable: true, value: {
    cancel: jest.fn(), speak: (utterance: any) => spoken.push(utterance),
  } });
  Object.defineProperty(window, 'SpeechSynthesisUtterance', { configurable: true, writable: true,
    value: class { text: string; constructor(text: string) { this.text = text; } } });
  const route = wilram.routes[0];
  try {
    render(<RouteInspector open onClose={jest.fn()} onMap={jest.fn()} route={route} variant="standard" />);
      expect(window.speechSynthesis).toBeDefined();
    expect(screen.getByText('App: Alle Hinweise vorlesen')).toBeEnabled();
    fireEvent.click(screen.getByText('App: Alle Hinweise vorlesen'));
    const expected = appGuidancePreview(route, listSteps(route)).rows.filter(r => r.appSpeech).map(r => r.appSpeech);
    for (let i = 0; i < expected.length; i++) {
      expect(spoken.map(s => s.text)).toEqual(expected.slice(0, i + 1));
      expect(spoken[i].text).toBe(expected[i]);
      act(() => spoken[i].onend());
    }
    expect(spoken).toHaveLength(expected.length);
    expect(spoken.some(s => s.text.includes('Keine Einzelansage'))).toBe(false);
  } finally {
    if (originalSpeech === undefined) delete (window as any).speechSynthesis;
    else Object.defineProperty(window, 'speechSynthesis', { configurable: true, writable: true, value: originalSpeech });
    if (originalUtterance === undefined) delete (window as any).SpeechSynthesisUtterance;
    else Object.defineProperty(window, 'SpeechSynthesisUtterance', { configurable: true, writable: true, value: originalUtterance });
  }
});

test('follows map route replacements, removal and reopening without a separate request', () => {
  const originalFetch = global.fetch;
  global.fetch = jest.fn();
  const props = { onClose: jest.fn(), onMap: jest.fn(), variant: 'standard' };
  const first = { distance: 147.2, legs: [{ steps }] };
  const nextStep = { ...step('turn', 'left', 160), name: 'Neue Beispielstra\u00dfe' };
  const next = { distance: 160, legs: [{ steps: [nextStep] }] };
  try {
    const view = render(<RouteInspector {...props} open route={first} />);
    expect(screen.getByText(/^147 m .*Manöver/)).toBeInTheDocument();
    view.rerender(<RouteInspector {...props} open route={next} />);
    expect(screen.getByText(/^160 m .*Manöver/)).toBeInTheDocument();
    expect(screen.queryByText('turn / right')).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('Hinweis 1 auf Karte'));
    expect(props.onMap).toHaveBeenCalledWith(nextStep);
    view.rerender(<RouteInspector {...props} open route={null} />);
    expect(screen.queryByText(/^160 m .*Manöver/)).not.toBeInTheDocument();
    expect(screen.getByText('Bitte zuerst eine Route auf der Karte berechnen.')).toBeInTheDocument();
    view.rerender(<RouteInspector {...props} open={false} route={next} />);
    view.rerender(<RouteInspector {...props} open route={next} />);
    expect(screen.getByText(/^160 m .*Manöver/)).toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  } finally { global.fetch = originalFetch; }
});

test('window can be moved with the keyboard and minimized without closing', () => {
  const onClose = jest.fn();
  render(<RouteInspector open onClose={onClose} onMap={jest.fn()} route={null} variant="standard" />);
  const dialog = screen.getByRole('dialog');
  const previousLeft = parseInt(dialog.style.left, 10);
  fireEvent.keyDown(screen.getByLabelText('Prüffenster verschieben, auch mit Pfeiltasten'), { key: 'ArrowRight' });
  expect(parseInt(dialog.style.left, 10)).toBe(previousLeft + 20);
  expect(dialog.style.resize).toBe('both');
  fireEvent.click(screen.getByText('Verkleinern'));
  expect(screen.getByText('Bitte zuerst eine Route auf der Karte berechnen.')).not.toBeVisible();
  expect(onClose).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText('Öffnen'));
  expect(screen.getByText('Bitte zuerst eine Route auf der Karte berechnen.')).toBeVisible();
});
