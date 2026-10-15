import React, { useState } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import RouteStops from './RouteStops';
test('stop selection, reordering and deletion keep ordered exact coordinates', async () => {
  const changed = jest.fn();
  function Harness() {
    const [stops, setStops] = useState<any[]>([]);
    return <RouteStops stops={stops} onChange={value => { changed(value); setStops(value); }} />;
  }
  render(<Harness />);
  fireEvent.click(screen.getByText('Zwischenziel hinzufügen'));
  fireEvent.change(screen.getByRole('combobox', { name: 'Zwischenziel 1' }), { target: { value: '48.1, 11.5' } });
  fireEvent.click(await screen.findByRole('option', { name: '48.1, 11.5' }));
  fireEvent.click(screen.getByText('Zwischenziel hinzufügen'));
  fireEvent.change(screen.getByRole('combobox', { name: 'Zwischenziel 2' }), { target: { value: '48.2, 11.6' } });
  fireEvent.click(await screen.findByRole('option', { name: '48.2, 11.6' }));
  fireEvent.click(screen.getByRole('button', { name: 'Zwischenziel 2 nach oben' }));
  expect(changed.mock.calls[changed.mock.calls.length - 1][0].map((p: any) => p.lat)).toEqual(['48.2', '48.1']);
  fireEvent.click(screen.getAllByText('Entfernen')[0]);
  expect(changed.mock.calls[changed.mock.calls.length - 1][0].map((p: any) => p.lat)).toEqual(['48.1']);
});
