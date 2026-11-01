import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MAP_BACKGROUND_PREFERENCE, useMapBackground } from './mapBackground';

function Example() {
  const [background, setBackground] = useMapBackground();
  return <button onClick={() => setBackground(background === 'standard' ? 'reduced' : 'standard')}>{background}</button>;
}

afterEach(() => { jest.restoreAllMocks(); window.localStorage.clear(); });

test('unknown stored choices fall back to Standard', () => {
  window.localStorage.setItem(MAP_BACKGROUND_PREFERENCE, 'obsolete');
  render(<Example />);
  expect(screen.getByRole('button').textContent).toBe('standard');
});

test('blocked storage keeps selection usable and recovers when storage returns', () => {
  const read = jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
  const write = jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
  render(<Example />);
  fireEvent.click(screen.getByRole('button'));
  expect(screen.getByRole('button').textContent).toBe('reduced');
  read.mockRestore();
  write.mockRestore();
  fireEvent.click(screen.getByRole('button'));
  expect(window.localStorage.getItem(MAP_BACKGROUND_PREFERENCE)).toBe('standard');
  fireEvent.click(screen.getByRole('button'));
  expect(window.localStorage.getItem(MAP_BACKGROUND_PREFERENCE)).toBe('reduced');
});
