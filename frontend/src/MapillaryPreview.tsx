import React from 'react';
import { mapillaryPreview, StreetProperties } from './streetDetails';

export default function MapillaryPreview({ properties }: { properties: StreetProperties }) {
  const preview = mapillaryPreview(properties);
  if (!preview) return null;
  return <figure className="street-mapillary">
    <iframe key={preview.id} title="Mapillary-Straßenansicht" src={preview.embedUrl}
      loading="lazy" referrerPolicy="no-referrer" allowFullScreen />
    <figcaption><a href={preview.url} target="_blank" rel="noopener noreferrer">Auf Mapillary ansehen</a></figcaption>
  </figure>;
}
