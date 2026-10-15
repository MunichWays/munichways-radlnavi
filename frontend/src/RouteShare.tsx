import React, { useEffect, useState } from 'react';
import { Button, Dialog, DialogActions, DialogContent, DialogTitle, TextField } from '@mui/material';
import QRCode from 'qrcode';
import { RouteTransfer } from './routeTransfer';

export default function RouteShare({ transfer }: { transfer: RouteTransfer | null }) {
  const [open, setOpen] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [link, setLink] = useState('');
  const [expires, setExpires] = useState('');
  const [qr, setQr] = useState('');
  const [error, setError] = useState('');
  useEffect(() => { setOpen(false); setBusy(false); setAccepted(false); setLink(''); setError(''); setQr(''); }, [transfer]);
  const close = () => { setOpen(false); setBusy(false); setAccepted(false); };
  useEffect(() => {
    if (!open || !accepted || !transfer) return;
    const controller = new AbortController();
    setBusy(true); setError('');
    (async () => {
      try {
        const response = await fetch(`${process.env.REACT_APP_BACKEND_URL || ''}/shared_routes`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(transfer), signal: controller.signal,
        });
        if (!response.ok) {
          const detail = await response.json().catch(() => ({}));
          const message = response.status === 503 && detail.detail === 'Route sharing is not configured'
            ? 'Das Teilen von Routen ist noch nicht eingerichtet. Bitte die Route als GPX herunterladen.'
            : response.status === 429
              ? 'Zu viele Links erstellt. Bitte später erneut versuchen oder die Route als GPX herunterladen.'
              : response.status === 413
                ? 'Diese Route ist zum Teilen zu groß. Bitte die Route als GPX herunterladen.'
                : 'Die Route konnte nicht geteilt werden. Bitte erneut versuchen oder als GPX herunterladen.';
          throw new Error(message);
        }
        const data = await response.json();
        const code = await QRCode.toDataURL(data.url, { width: 280, margin: 2 });
        if (!controller.signal.aborted) { setLink(data.url); setExpires(data.expiresAt); setQr(code); }
      } catch (err) {
        if (!controller.signal.aborted) { setError((err as Error).message); setAccepted(false); }
      } finally { if (!controller.signal.aborted) setBusy(false); }
    })();
    return () => controller.abort();
  }, [open, accepted, transfer]);
  return <>
    <Button disabled={!transfer} onClick={() => { setOpen(true); setBusy(false); setError(''); setAccepted(false); setLink(''); setQr(''); }}>In App öffnen / teilen</Button>
    <Dialog open={open} onClose={close}>
      <DialogTitle>Route auf dem Handy öffnen</DialogTitle>
      <DialogContent>
        <p>Beim Teilen werden Strecke und geplante Orte für 90 Tage gespeichert. Jeder mit dem Link kann die Route öffnen.</p>
        {error && <p role="alert">{error}</p>}
        {busy && <p role="status">Link wird erstellt …</p>}
        {link && <>
          <img src={qr} alt="QR-Code zum Öffnen dieser Route" width={280} height={280} />
          <p>In der MunichWays App „Route“ → „Route importieren“ → „QR-Code scannen“ wählen. Anschließend die Route prüfen und speichern.</p>
          <p>Alternativ den Teilen-Link in der App unter „Route importieren“ einfügen.</p>
          <TextField label="Teilen-Link" value={link} fullWidth InputProps={{ readOnly: true }} />
          <Button onClick={async () => { try { await navigator.clipboard.writeText(link); } catch (_) { setError('Bitte den Link im Textfeld markieren und kopieren.'); } }}>Link kopieren</Button>
          <p>Gültig bis {new Date(expires).toLocaleDateString('de-DE')}. Die in der App gespeicherte Kopie bleibt erhalten.</p>
        </>}
      </DialogContent>
      <DialogActions>
        <Button onClick={close}>Schließen</Button>
        {!link && <Button disabled={busy} onClick={() => setAccepted(true)}>Link erstellen</Button>}
      </DialogActions>
    </Dialog>
  </>;
}
