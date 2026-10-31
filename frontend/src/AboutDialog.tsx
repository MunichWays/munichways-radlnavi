import React, { useEffect, useState } from 'react';
import { Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, Link, Typography } from '@mui/material';

function ExternalLink({ href, children }: { href: string; children: React.ReactNode }) {
  return <Link href={href} target="_blank" rel="noopener noreferrer">{children}</Link>;
}

export default function AboutDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const readViewport = () => ({
    width: window.visualViewport?.width || document.documentElement.clientWidth || window.innerWidth,
    height: window.visualViewport?.height || document.documentElement.clientHeight || window.innerHeight,
    left: window.visualViewport?.offsetLeft || 0,
    top: window.visualViewport?.offsetTop || 0,
  });
  const [viewport, setViewport] = useState(readViewport);
  useEffect(() => {
    const fit = () => setViewport(readViewport());
    fit();
    window.addEventListener('resize', fit);
    window.visualViewport?.addEventListener('resize', fit);
    window.visualViewport?.addEventListener('scroll', fit);
    return () => {
      window.removeEventListener('resize', fit);
      window.visualViewport?.removeEventListener('resize', fit);
      window.visualViewport?.removeEventListener('scroll', fit);
    };
  }, [open]);
  return <Dialog open={open} onClose={onClose} aria-labelledby="radlnavi-info-title" maxWidth={false}
    sx={{ width: viewport.width, height: viewport.height, left: viewport.left, top: viewport.top, right: 'auto', bottom: 'auto' }}
    PaperProps={{ sx: { width: 560, maxWidth: 'calc(100% - 24px)', m: 1.5,
      maxHeight: Math.min(800, viewport.height - 24), borderRadius: 2 } }}>
    <DialogTitle component="div" sx={{ pt: 2.5, pb: 1, pr: 6 }}>
      <Box component="img" src="/logo-munichways.svg" alt="MunichWays" sx={{ width: 112, height: 32, objectFit: 'contain', objectPosition: 'left', mb: 1 }} />
      <Typography id="radlnavi-info-title" component="h1" variant="h5" sx={{ fontWeight: 700, fontSize: { xs: '1.3rem', sm: '1.5rem' }, lineHeight: 1.2 }}>
        Wie radfreundlich sind Münchens Straßen?
      </Typography>
      <IconButton aria-label="Infofenster schließen" onClick={onClose} sx={{ position: 'absolute', top: 8, right: 8 }}>
        <span aria-hidden="true">×</span>
      </IconButton>
    </DialogTitle>
    <DialogContent sx={{ px: 3, pb: 1, overflowY: 'auto', fontSize: '0.95rem', lineHeight: 1.5,
      '& p': { my: 1.5 }, '& details': { borderTop: '1px solid', borderColor: 'divider', py: 1.25 },
      '& summary': { cursor: 'pointer', fontWeight: 600, borderRadius: 0.5 },
      '& summary:focus-visible': { outline: '2px solid #00769B', outlineOffset: 3 } }}>
      <p><strong>Mit RadlNavi die angenehmen Wege entdecken.</strong></p>
      <p>Wo fahren Münchner Radler*innen gerne – und wo wird es stressig? RadlNavi zeigt Euch die Bewertung der Straßen und Wege sowie das bestehende <strong>MunichWays RadlVorrang-Netz</strong>.</p>
      <p>Bekannte Strecken wie der Isarradweg oder die Radl-Stammstrecke gehören bereits dazu. Zusammen bilden sie ein Netz für den Alltag: auf vielen Abschnitten gut befahrbar, aber noch mit Lücken.</p>
      <Box component="p" sx={{ bgcolor: '#EAF8FD', p: 1.5, borderRadius: 1 }}>
        👉 <strong>Rechtsklick am PC oder lange drücken am Handy auf einen Straßenabschnitt, um seine Bewertung und weitere Informationen zu sehen.</strong>
      </Box>
      <details>
        <summary>Was bedeuten die Farben?</summary>
        <p>Das <strong>Happy-Bike-Level</strong> beschreibt, wie angenehm oder stressig sich ein Straßenabschnitt mit dem Rad fahren lässt.</p>
        <Box component="img" loading="lazy" src="https://www.munichways.de/img/legende/Legende_RadlVorrang-Netz.png"
          alt="Farblegende des Happy-Bike-Levels" sx={{ display: 'block', width: '100%', height: 'auto', my: 1.5 }} />
        <p><ExternalLink href="https://www.munichways.de/img/legende/Legende_RadlVorrang-Netz.png">Legende ansehen</ExternalLink> · <ExternalLink href="https://www.munichways.de/berwertungskriterien-radwege/">Ausführliche Bewertungskriterien</ExternalLink></p>
      </details>
      <details>
        <summary>Über das RadlVorrang-Netz</summary>
        <p>MunichWays macht sichtbar, welche Wege sich heute für den Alltagsradverkehr eignen und wo Verbesserungen fehlen. Die Karte zeigt den erfassten Ist-Zustand – ein durchgängiges, angenehmes Netz ist unser Ziel.</p>
        <p><ExternalLink href="https://www.munichways.de/radlvorrangnetz/">Mehr zum RadlVorrang-Netz</ExternalLink> · <ExternalLink href="https://www.munichways.de">Über MunichWays</ExternalLink></p>
      </details>
      <details>
        <summary>Daten &amp; Aktualisierungen</summary>
        <p>Die Informationen stammen aus OpenStreetMap und der MunichWays-Masterliste. Hinweise und Änderungen übernehmen wir regelmäßig in diese Datenbestände.</p>
        <p><ExternalLink href="https://docs.google.com/document/d/1qp7hu_GjmsNlzEa-FbmM8N1cUy9PFemExsIySHt3-zg/edit?usp=sharing">Änderungsprotokoll</ExternalLink> · <ExternalLink href="https://drive.google.com/drive/folders/1u4Q1dyMuB1n0j2_YgQxiK_xfLVC1VYE9?usp=sharing">Daten herunterladen</ExternalLink></p>
      </details>
      <Typography component="p" variant="body2" color="text.secondary" sx={{ borderTop: '1px solid', borderColor: 'divider', pt: 1.5 }}>
        Du kannst dieses Fenster jederzeit über das <strong>Hauptmenü → Über RadlNavi</strong> wieder öffnen.
      </Typography>
      <Typography component="p" variant="body2">
        Fragen, Hinweise oder Ideen? <Link href="mailto:mail@munichways.de?subject=Feedback%20zu%20RadlNavi">Feedback an mail@munichways.de</Link>
      </Typography>
    </DialogContent>
    <DialogActions sx={{ px: 3, py: 2 }}>
      <Button variant="contained" onClick={onClose}>Karte entdecken</Button>
    </DialogActions>
  </Dialog>;
}
