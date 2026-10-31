import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import PriorityNetworkLayer from './PriorityNetworkLayer';
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
