export interface NamedPlace {
  display_name?: string;
  name?: string;
  address?: Record<string, string>;
}

/** Keep the address useful without repeating the administrative hierarchy. */
export function compactPlaceName(place: NamedPlace): string {
  const address = place.address;
  if (!address) return (place.display_name || '').trim();
  const value = (key: string) => (address[key] || '').trim();
  const street = value('road') || value('pedestrian') || value('street') || value('place');
  const streetAddress = [street, value('house_number')].filter(Boolean).join(' ');
  const city = value('city') || value('town') || value('village') || value('municipality');
  const cityAddress = [value('postcode'), city].filter(Boolean).join(' ');
  const name = (place.name || place.display_name?.split(',')[0] || '').trim();
  const localArea = value('neighbourhood') || value('quarter') || value('suburb');
  const parts = [name === street || name === streetAddress || name === value('house_number') ? '' : name,
    streetAddress, cityAddress || localArea].filter(Boolean);
  const seen = new Set<string>();
  return parts.filter(part => {
    const key = part.toLocaleLowerCase('de');
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }).join(', ') || (place.display_name || '').trim();
}

export function withCompactPlaceName<T extends NamedPlace>(place: T): T {
  return { ...place, display_name: compactPlaceName(place) };
}
