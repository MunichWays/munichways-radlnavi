import { useEffect, useState } from 'react';
import type { MapBackground } from './MapBackgroundControl';

export const MAP_BACKGROUND_PREFERENCE = 'radlnavi.mapBackground';

function readPreference(): MapBackground {
  try {
    const stored = window.localStorage.getItem(MAP_BACKGROUND_PREFERENCE);
    return stored === 'reduced' || stored === 'bavaria-aerial' ? stored : 'standard';
  } catch {
    return 'standard';
  }
}

export function useMapBackground() {
  const [background, setBackground] = useState<MapBackground>(readPreference);
  useEffect(() => {
    try {
      window.localStorage.setItem(MAP_BACKGROUND_PREFERENCE, background);
    } catch {
      // Browsers may block storage. The map choice still works for this visit.
    }
  }, [background]);
  return [background, setBackground] as const;
}
