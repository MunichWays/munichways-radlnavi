import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import StreetDetailsControl from './StreetDetailsDialog';

const mockSearch = jest.fn();
const mockDetails = jest.fn();
const mockDispose = jest.fn();
jest.mock('./streetDetailsClient', () => ({ StreetDetailsClient: function () {
  return { search: mockSearch, details: mockDetails, dispose: mockDispose };
} }));
const manifest = { snapshot: 'a'.repeat(64), retrievedAt: '2026-10-31T10:00:00Z' };
const candidate = (id = '123', name = 'Altostraße') => ({ id: `osm_${id}`, properties: { osm_name: name },
  geometry: { type: 'LineString', coordinates: [[11.5, 48.1], [11.502, 48.1]] }, distance: 0 });
const query = { lat: 48.1, lng: 11.501, zoom: 16 };
beforeEach(() => {
  jest.clearAllMocks();
  mockSearch.mockResolvedValue({ manifest, candidates: [candidate()] });
  mockDetails.mockResolvedValue({ osm_id: '123', osm_name: 'Altostraße', osm_class_bicycle: '-2',
    munichways_current: 'Viel befahrene Straße', munichways_target: 'Radweg verbreitern', osm_width: '2.5',
    munichways_links: '<a href="https://example.org">Weiterlesen</a><a href="javascript:bad()">Unsicher</a>' });
});

test('opens details, highlights the full line, preserves fields and safe links, and clears on Escape', async () => {
  const highlight = jest.fn();
  render(<StreetDetailsControl query={query} onHighlight={highlight} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Details anzeigen' }));
  const dialog = await screen.findByRole('dialog');
  expect(await within(dialog).findByText('Altostraße')).toBeInTheDocument();
  expect(dialog).toHaveTextContent('Sehr stressig · OSM class:bicycle: -2');
  expect(dialog).toHaveTextContent('Viel befahrene Straße');
  expect(dialog).toHaveTextContent('Radweg verbreitern');
  expect(dialog).toHaveTextContent('2.5 Meter');
  const link = within(dialog).getByRole('link', { name: 'Weiterlesen', hidden: true });
  expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  expect(within(dialog).queryByText('Unsicher')).not.toBeInTheDocument();
  expect(highlight).toHaveBeenLastCalledWith(candidate());
  fireEvent.keyDown(dialog, { key: 'Escape', code: 'Escape' });
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(highlight).toHaveBeenLastCalledWith(null);
});
test('requires a choice for parallel streets and fetches only the selected candidate', async () => {
  mockSearch.mockResolvedValue({ manifest, candidates: [candidate(), candidate('224', 'Nebenweg')] });
  const highlight = jest.fn();
  render(<StreetDetailsControl query={query} onHighlight={highlight} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Details anzeigen' }));
  expect(mockDetails).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: /Nebenweg.*OSM 224/ }));
  await waitFor(() => expect(mockDetails).toHaveBeenCalledWith(manifest, 'osm_224', expect.any(AbortSignal)));
  expect(highlight).toHaveBeenLastCalledWith(candidate('224', 'Nebenweg'));
});
test('stale search and detail replies cannot replace a new point or a closed dialog', async () => {
  let resolveSearch: (v: any) => void = () => {};
  mockSearch.mockReturnValueOnce(new Promise(resolve => { resolveSearch = resolve; }));
  const highlight = jest.fn();
  const view = render(<StreetDetailsControl query={query} onHighlight={highlight} />);
  view.rerender(<StreetDetailsControl query={{ ...query, lng: 11.6 }} onHighlight={highlight} />);
  expect(await screen.findByRole('button', { name: 'Details anzeigen' })).toBeInTheDocument();
  await act(async () => resolveSearch({ manifest, candidates: [] }));
  expect(screen.getByRole('button', { name: 'Details anzeigen' })).toBeInTheDocument();
  let resolveDetails: (v: any) => void = () => {};
  mockDetails.mockReturnValueOnce(new Promise(resolve => { resolveDetails = resolve; }));
  fireEvent.click(screen.getByRole('button', { name: 'Details anzeigen' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Schließen' }));
  await act(async () => resolveDetails({ osm_name: 'Verspätet' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(highlight).toHaveBeenLastCalledWith(null);
  view.unmount();
  expect(mockDispose).toHaveBeenCalledTimes(1);
});
test('distinguishes zoom, no match and loading failures, and retries a failed detail load', async () => {
  const highlight = jest.fn();
  const view = render(<StreetDetailsControl query={{ ...query, zoom: 13 }} onHighlight={highlight} />);
  expect(screen.getByText(/bitte hineinzoomen/)).toBeInTheDocument();
  expect(mockSearch).not.toHaveBeenCalled();
  mockSearch.mockResolvedValueOnce({ manifest, candidates: [] });
  view.rerender(<StreetDetailsControl query={query} onHighlight={highlight} />);
  expect(await screen.findByText(/keine V20-Streckendetails/)).toBeInTheDocument();
  mockSearch.mockRejectedValueOnce(new Error('Netzwerkfehler'));
  view.rerender(<StreetDetailsControl query={{ ...query, lng: 11.6 }} onHighlight={highlight} />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Netzwerkfehler');
  fireEvent.click(screen.getByRole('button', { name: 'Streckensuche wiederholen' }));
  mockDetails.mockRejectedValueOnce(new Error('Ladefehler'));
  fireEvent.click(await screen.findByRole('button', { name: 'Details anzeigen' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Ladefehler');
  fireEvent.click(screen.getByRole('button', { name: 'Erneut versuchen' }));
  expect(await screen.findByText('Altostraße')).toBeInTheDocument();
});
