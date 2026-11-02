import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import PriorityNetworkLayer from './PriorityNetworkLayer';
import jahnstrasse from './fixtures/street-olching-jahnstrasse.json';
const mockAdd = jest.fn();
const mockGeoJSON = jest.fn();
jest.mock('leaflet', () => ({ geoJSON: (...args: unknown[]) => mockGeoJSON(...args), canvas: () => ({}) }));
const originalFetch = global.fetch;
afterEach(() => { global.fetch = originalFetch; });

test('loads only the versioned priority collection, removes it when hidden, and supports retry', async () => {
  const layer = { addTo: mockAdd };
  mockGeoJSON.mockReturnValue(layer);
  const map = { removeLayer: jest.fn() };
  const collection = { type: 'FeatureCollection', features: [] };
  global.fetch = jest.fn().mockRejectedValueOnce(new Error('offline'));
  const { rerender, unmount } = render(<PriorityNetworkLayer map={map} visible />);
  expect(await screen.findByRole('alert')).toHaveTextContent('konnte nicht geladen');
  (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true, json: async () => ({ snapshot: 'a'.repeat(64) }) })
    .mockResolvedValueOnce({ ok: true, json: async () => collection });
  fireEvent.click(screen.getByRole('button', { name: 'Erneut laden' }));
  await waitFor(() => expect(mockAdd).toHaveBeenCalledWith(map));
  expect(global.fetch).toHaveBeenLastCalledWith(`/street-details/${'a'.repeat(64)}/priority-network-v1.json`, expect.anything());
  const options = mockGeoJSON.mock.calls[0][1];
  expect(options.interactive).toBe(false);
  expect(options.style({ properties: { osm_class_bicycle: '-1' } })).toEqual({ color: '#F44336', weight: 1.5, dashArray: '6 5' });
  rerender(<PriorityNetworkLayer map={map} visible={false} />);
  expect(map.removeLayer).toHaveBeenCalledWith(layer);
  expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  unmount();
});

test('a response arriving after switching back cannot add an obsolete layer', async () => {
  let resolve: (value: unknown) => void = () => {};
  global.fetch = jest.fn().mockImplementation(() => new Promise(done => { resolve = done; }));
  const { rerender } = render(<PriorityNetworkLayer map={{ removeLayer: jest.fn() }} visible />);
  rerender(<PriorityNetworkLayer map={null} visible={false} />);
  mockAdd.mockClear();
  resolve({ ok: true, json: async () => ({ snapshot: 'a'.repeat(64) }) });
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
  expect(mockAdd).not.toHaveBeenCalled();
});

test.each([['all', 'geometry.json'], ['munichways-only', 'munichways-only-v1.json']] as const)(
  '%s loads the matching V20 collection and renders exported MunichWays ratings', async (source, file) => {
    mockGeoJSON.mockReturnValue({ addTo: mockAdd });
    global.fetch = jest.fn().mockResolvedValueOnce({ ok: true, json: async () => ({ snapshot: 'a'.repeat(64) }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ type: 'FeatureCollection', features: [] }) });
    render(<PriorityNetworkLayer map={{ removeLayer: jest.fn() }} visible source={source} />);
    await waitFor(() => expect(mockGeoJSON).toHaveBeenCalled());
    expect(global.fetch).toHaveBeenLastCalledWith(`/street-details/${'a'.repeat(64)}/${file}`, expect.anything());
    const options = mockGeoJSON.mock.calls[0][1];
    expect(options.style({ properties: { munichways_color: 'gelb' } }).color).toBe('#FFD000');
    if (source === 'munichways-only') {
      expect(await screen.findByRole('status')).toHaveTextContent('Keine Strecken ohne OSM-ID');
    }
  });

test('all ratings draws the V20 Jahnstraße as red without OSM bicycle tags or MunichWays details', async () => {
  const feature = { ...jahnstrasse, id: 'osm_8059921' };
  const collection = { type: 'FeatureCollection', features: [feature] };
  mockGeoJSON.mockReturnValue({ addTo: mockAdd });
  global.fetch = jest.fn().mockResolvedValueOnce({ ok: true, json: async () => ({ snapshot: 'a'.repeat(64) }) })
    .mockResolvedValueOnce({ ok: true, json: async () => collection });
  render(<PriorityNetworkLayer map={{ removeLayer: jest.fn() }} visible source="all" />);
  await waitFor(() => expect(mockGeoJSON).toHaveBeenCalledWith(collection, expect.anything()));
  expect(mockGeoJSON.mock.calls[0][1].style(feature)).toEqual({ color: '#F44336', weight: 1.5, dashArray: '6 5' });
});
