import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import RouteInspector, { listSteps, parseCoordinates } from './RouteInspector';

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

test('accepts user coordinate order and rejects missing or invalid coordinates', () => {
  expect(parseCoordinates('[48.145395, 11.520751]')).toEqual([11.520751, 48.145395]);
  for (const value of ['48,', 'foo, 11', '91, 11', '48, 181', '48, 11, 2']) {
    expect(() => parseCoordinates(value)).toThrow();
  }
});

test('loads raw maneuvers, recovers from request errors and passes exact step to map', async () => {
  const originalFetch = global.fetch;
  const onMap = jest.fn();
  const onClose = jest.fn();
  global.fetch = jest.fn()
    .mockResolvedValueOnce({ ok: false, status: 503 })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ code: 'Ok', routes: [{ distance: 147.2, legs: [{ steps }] }] }) });
  try {
    render(<RouteInspector open onClose={onClose} onMap={onMap} route={null} variant="standard" />);
    fireEvent.click(screen.getByText('Route prüfen'));
    expect(await screen.findByRole('alert')).toHaveTextContent('503');
    fireEvent.click(screen.getByText('Route prüfen'));
    await screen.findByText('continue / left');
    expect(screen.getByText('turn / right')).toBeInTheDocument();
    expect(global.fetch).toHaveBeenLastCalledWith(expect.stringContaining('11.520751,48.145395;11.522572,48.145413'), expect.anything());
    fireEvent.click(screen.getByText('Hinweis 2 auf Karte'));
    expect(onMap).toHaveBeenCalledWith(steps[1]);
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog')).toHaveAttribute('aria-modal', 'false');
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  } finally { global.fetch = originalFetch; }
});

test('reads every instruction in order and stops the sequence on close', () => {
  const originalSpeech = window.speechSynthesis;
  const originalUtterance = window.SpeechSynthesisUtterance;
  const spoken: any[] = [];
  Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: {
    cancel: jest.fn(), speak: (utterance: any) => spoken.push(utterance),
  } });
  Object.defineProperty(window, 'SpeechSynthesisUtterance', { configurable: true,
    value: class { text: string; constructor(text: string) { this.text = text; } } });
  const props = { onClose: jest.fn(), onMap: jest.fn(), route: { steps, distance: 147.2 }, variant: 'standard' };
  try {
    const view = render(<RouteInspector {...props} open />);
    fireEvent.click(screen.getByText('Aktuelle Kartenroute übernehmen'));
    fireEvent.click(screen.getByText('Alle Hinweise vorlesen'));
    expect(spoken).toHaveLength(1);
    act(() => spoken[0].onend());
    expect(spoken[1].text).toMatch(/links/i);
    act(() => spoken[1].onend());
    expect(spoken[2].text).toMatch(/rechts/i);
    view.rerender(<RouteInspector {...props} open={false} />);
    act(() => spoken[2].onend());
    expect(spoken).toHaveLength(3);
    expect(window.speechSynthesis.cancel).toHaveBeenCalled();
    view.unmount();
  } finally {
    Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: originalSpeech });
    Object.defineProperty(window, 'SpeechSynthesisUtterance', { configurable: true, value: originalUtterance });
  }
});

test('uses current map endpoints on opening and ignores an older pending response', async () => {
  const originalFetch = global.fetch;
  let finishOld: (response: any) => void = () => {};
  global.fetch = jest.fn()
    .mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve; }))
    .mockResolvedValueOnce({ ok: true, json: async () => ({ code: 'Ok', routes: [{ distance: 160, legs: [{ steps }] }] }) });
  const props = { onClose: jest.fn(), onMap: jest.fn(), route: null, variant: 'standard',
    startPosition: { lat: '48.139050', lon: '11.576817' }, endPosition: { lat: '48.138800', lon: '11.577644' } };
  try {
    const view = render(<RouteInspector {...props} open={false} />);
    expect(global.fetch).not.toHaveBeenCalled();
    view.rerender(<RouteInspector {...props} open />);
    expect(screen.getByLabelText('Start: Breite, Länge')).toHaveValue('48.139050, 11.576817');
    expect(screen.getByLabelText('Ziel: Breite, Länge')).toHaveValue('48.138800, 11.577644');
    expect(global.fetch).toHaveBeenLastCalledWith(expect.stringContaining('11.576817,48.13905;11.577644,48.1388'), expect.anything());
    const firstSignal = (global.fetch as jest.Mock).mock.calls[0][1].signal;
    view.rerender(<RouteInspector {...props} open={false} />);
    expect(firstSignal.aborted).toBe(true);
    view.rerender(<RouteInspector {...props} open startPosition={{ lat: '48.140563', lon: '11.568148' }}
      endPosition={{ lat: '48.140709', lon: '11.570143' }} />);
    await screen.findByText(/160 m · 4 Manöver/);
    await act(async () => finishOld({ ok: true, json: async () => ({ code: 'Ok', routes: [{ distance: 999, legs: [{ steps }] }] }) }));
    expect(screen.queryByText(/999 m ·/)).not.toBeInTheDocument();
    expect(screen.getByLabelText('Start: Breite, Länge')).toHaveValue('48.140563, 11.568148');
    fireEvent.change(screen.getByLabelText('Start: Breite, Länge'), { target: { value: '48.1, 11.5' } });
    expect(global.fetch).toHaveBeenCalledTimes(2);
    view.unmount();
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
  expect(screen.getByLabelText('Start: Breite, Länge')).not.toBeVisible();
  expect(onClose).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText('Öffnen'));
  expect(screen.getByLabelText('Start: Breite, Länge')).toBeVisible();
});
