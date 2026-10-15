import React from 'react';
import { TextEncoder, TextDecoder } from 'util';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import RouteShare from './RouteShare';
import fixture from './fixtures/route-transfer.json';
Object.assign(globalThis, { TextEncoder, TextDecoder });
jest.mock('qrcode', () => ({ toDataURL: async () => 'data:image/png;base64,qr' }));

test('missing production configuration explains the GPX fallback and allows retry', async () => {
  const original = global.fetch;
  global.fetch = jest.fn().mockResolvedValueOnce({ ok: false, status: 503,
    json: async () => ({ detail: 'Route sharing is not configured' })
  }).mockResolvedValueOnce({ ok: true, json: async () => ({
    url: 'https://radlnavi.munichways.de/r/test', expiresAt: '2027-01-12T00:00:00Z'
  }) });
  try {
    render(<RouteShare transfer={fixture as any} />);
    fireEvent.click(screen.getByText('In App öffnen / teilen'));
    fireEvent.click(screen.getByText('Link erstellen'));
    expect(await screen.findByRole('alert')).toHaveTextContent('noch nicht eingerichtet');
    expect(screen.getByRole('alert')).toHaveTextContent('als GPX herunterladen');
    fireEvent.click(screen.getByText('Link erstellen'));
    expect(await screen.findByLabelText('Teilen-Link')).toHaveValue('https://radlnavi.munichways.de/r/test');
  } finally { global.fetch = original; }
});
test('sharing requires explicit action and can recover from a temporary storage error', async () => {
  const original = global.fetch;
  global.fetch = jest.fn().mockResolvedValueOnce({ ok: false, json: async () => ({}) }).mockResolvedValueOnce({ ok: true, json: async () => ({ url: 'https://radlnavi.munichways.de/r/test', expiresAt: '2027-01-12T00:00:00Z' }) });
  try {
    render(<RouteShare transfer={fixture as any} />);
    fireEvent.click(screen.getByText('In App öffnen / teilen'));
    expect(screen.getByText(/für 90 Tage gespeichert/)).toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText('Link erstellen'));
    expect(await screen.findByRole('alert')).toHaveTextContent('erneut versuchen');
    fireEvent.click(screen.getByText('Link erstellen'));
    expect(await screen.findByRole('img', { name: 'QR-Code zum Öffnen dieser Route' })).toBeInTheDocument();
    expect(screen.getByLabelText('Teilen-Link')).toHaveValue('https://radlnavi.munichways.de/r/test');
  } finally { global.fetch = original; }
});
test('closing a pending share leaves the next attempt usable', async () => {
  const original = global.fetch;
  global.fetch = jest.fn().mockImplementationOnce(() => new Promise(() => {})).mockResolvedValueOnce({ ok: false, json: async () => ({}) });
  try {
    render(<RouteShare transfer={fixture as any} />);
    fireEvent.click(screen.getByText('In App öffnen / teilen'));
    fireEvent.click(screen.getByText('Link erstellen'));
    await screen.findByRole('status');
    fireEvent.click(screen.getByText('Schließen'));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    fireEvent.click(screen.getByText('In App öffnen / teilen'));
    expect(screen.getByText('Link erstellen')).toBeEnabled();
    fireEvent.click(screen.getByText('Link erstellen'));
    expect(await screen.findByRole('alert')).toBeInTheDocument();
  } finally { global.fetch = original; }
});
