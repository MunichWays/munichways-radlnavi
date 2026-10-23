import { NamedPlace, withCompactPlaceName } from './placeName';

interface Entrance {
  type: string;
  lat: string;
  lon: string;
  extratags?: Record<string, string>;
}

interface AddressPlace extends NamedPlace {
  lat: string;
  lon: string;
  category?: string;
  type?: string;
  extratags?: Record<string, string>;
  entrances?: Entrance[] | null;
}

const normalize = (value?: string) => (value || '').trim().toLocaleLowerCase('de');
const houseNumber = (place: AddressPlace) => normalize(place.address?.house_number);
const isHouseEntrance = (type?: string) => ['yes', 'home', 'main', 'shop'].includes(type || '');
const isEntrance = (place: AddressPlace) =>
  (place.category === 'entrance' && isHouseEntrance(place.type)) || isHouseEntrance(place.extratags?.entrance);

function sameAddress(a: AddressPlace, b: AddressPlace): boolean {
  const street = (p: AddressPlace) => normalize(p.address?.road || p.address?.pedestrian || p.address?.street || p.address?.place);
  const city = (p: AddressPlace) => normalize(p.address?.city || p.address?.town || p.address?.village || p.address?.municipality);
  return !!houseNumber(a) && houseNumber(a) === houseNumber(b) && !!street(a) && street(a) === street(b)
    && !!city(a) && city(a) === city(b)
    && (!a.address?.postcode || !b.address?.postcode || a.address.postcode === b.address.postcode);
}

/** Keep search ranking and labels, but route matching addresses to their entrance. */
export function preferEntrances<T extends AddressPlace>(places: T[], query = ''): T[] {
  return places.map(original => {
    // OSM buildings can contain several addresses, e.g. "19,21,23,25".
    const numbers = houseNumber(original).split(/[,;]/).map(normalize);
    const requested = numbers.filter(number => normalize(query).split(/[\s,;]+/).includes(number));
    const place = numbers.length > 1 && requested.length === 1
      ? { ...original, address: { ...original.address, house_number: requested[0] } }
      : original;
    if (isEntrance(place) || !houseNumber(place)) return withCompactPlaceName(place);
    const match = places.find(candidate => isEntrance(candidate) && sameAddress(place, candidate));
    const entrance = match || place.entrances?.find(candidate => isHouseEntrance(candidate.type)
      && normalize(candidate.extratags?.['addr:housenumber']) === houseNumber(place));
    return withCompactPlaceName(entrance
      ? { ...place, lat: entrance.lat, lon: entrance.lon }
      : place);
  });
}
