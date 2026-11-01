import React, { useState } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import MapBackgroundControl, { MapBackground } from './MapBackgroundControl';

function Example({ onChange = () => {} }: { onChange?: (value: MapBackground) => void }) {
  const [background, setBackground] = useState<MapBackground>('standard');
  return <MapBackgroundControl value={background} onChange={value => {
    onChange(value);
    setBackground(value);
  }} />;
}

test('selects one background and closes the menu without another callback for the active choice', async () => {
  const changed = jest.fn();
  render(<Example onChange={changed} />);
  const button = screen.getByRole('button', { name: 'Kartenansicht auswählen' });
  expect(button).toHaveAttribute('aria-expanded', 'false');
  fireEvent.click(button);
  expect(screen.getByRole('menuitemradio', { name: 'Standard' })).toHaveAttribute('aria-checked', 'true');
  fireEvent.click(screen.getByRole('menuitemradio', { name: 'Reduziert' }));
  expect(changed).toHaveBeenCalledTimes(1);
  expect(changed).toHaveBeenLastCalledWith('reduced');
  await waitFor(() => expect(screen.queryByRole('menu')).not.toBeInTheDocument());
  fireEvent.click(button);
  expect(screen.getByRole('menuitemradio', { name: 'Reduziert' })).toHaveAttribute('aria-checked', 'true');
  fireEvent.click(screen.getByRole('menuitemradio', { name: 'Reduziert' }));
  expect(changed).toHaveBeenCalledTimes(1);
  await waitFor(() => expect(screen.queryByRole('menu')).not.toBeInTheDocument());
  fireEvent.click(button);
  fireEvent.click(screen.getByRole('menuitemradio', { name: 'Standard' }));
  expect(changed).toHaveBeenLastCalledWith('standard');
});

test('Escape dismisses the menu without changing the background and restores focus', async () => {
  const changed = jest.fn();
  render(<Example onChange={changed} />);
  const button = screen.getByRole('button', { name: 'Kartenansicht auswählen' });
  act(() => button.focus());
  fireEvent.click(button);
  fireEvent.keyDown(screen.getByRole('menu'), { key: 'Escape' });
  await waitFor(() => expect(screen.queryByRole('menu')).not.toBeInTheDocument());
  expect(changed).not.toHaveBeenCalled();
  expect(button).toHaveFocus();
});
