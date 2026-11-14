"""Reviewed, localized junction sequences; no routing or TTS execution here."""
from math import atan2, cos, degrees, hypot, radians


def localized(value, limit):
    if (not isinstance(value, dict) or set(value) != {'de', 'en'} or
        any(not isinstance(text, str) or not text.strip() or len(text) > limit
            for text in value.values())):
        raise ValueError('Invalid localized sequence instruction')


def anchor_on_line(line, location, minimum=0, maximum=float('inf')):
    from .big_junctions import meters
    mx = 111320 * cos(radians(location[1]))
    best, distance = None, 0.0
    for index, (a, b) in enumerate(zip(line, line[1:])):
        ax, ay = (a[0]-location[0])*mx, (a[1]-location[1])*111320
        dx, dy = (b[0]-a[0])*mx, (b[1]-a[1])*111320
        length = hypot(dx, dy)
        fraction = max(0, min(1, -(ax*dx+ay*dy)/(length*length))) if length else 0
        if fraction < 1e-12:
            fraction = 0
        elif fraction > 1 - 1e-12:
            fraction = 1
        gap = hypot(ax+fraction*dx, ay+fraction*dy)
        station = distance+fraction*meters(a, b)
        # At a shared vertex both adjacent segments describe the same anchor.
        # Keep the earlier segment for sub-micrometre ties: platform libm
        # rounding must not select the next segment instead.
        if minimum <= station <= maximum and (best is None or gap < best[0] - 1e-7):
            best = (gap, dict(location=list(location), geometrySegmentIndex=index,
                segmentFraction=fraction, distanceAlongLegMeters=station))
        distance += meters(a, b)
    if best is None or best[0] > .75:
        raise ValueError('Sequence checkpoint not on matched route')
    return best[1]


def bearing(path):
    a, b = path[0], path[-1]
    return degrees(atan2((b[0]-a[0])*cos(radians(a[1])), b[1]-a[1])) % 360


def validate_sequence(sequence, movement, ring):
    from .big_junctions import inside, meters, points
    if not isinstance(sequence, dict) or sequence.get('version') != 1:
        raise ValueError('Unsupported junction sequence')
    review = sequence.get('review', {})
    if review.get('status') != 'approved' or not review.get('date') or not review.get('evidence'):
        raise ValueError('Sequence requires explicit review')
    localized(sequence.get('advance'), 240)
    localized(sequence.get('display'), 80)
    checkpoints = sequence.get('checkpoints')
    if not isinstance(checkpoints, list) or not 1 <= len(checkpoints) <= 6:
        raise ValueError('Invalid sequence checkpoints')
    identifiers, previous = set(), -5.0
    for checkpoint in checkpoints:
        identifier = checkpoint.get('id')
        if not isinstance(identifier, str) or not identifier or len(identifier) > 80 or identifier in identifiers:
            raise ValueError('Duplicate or invalid checkpoint id')
        identifiers.add(identifier)
        if checkpoint.get('modifier') not in ('left', 'right', 'straight', 'uturn'):
            raise ValueError('Invalid checkpoint modifier')
        localized(checkpoint.get('instruction'), 120)
        if 'alignedInstruction' in checkpoint:
            localized(checkpoint['alignedInstruction'], 120)
        location, = points({'type': 'LineString', 'coordinates': [checkpoint['location']]})
        if not inside(location, ring):
            raise ValueError('Checkpoint outside crossing')
        anchor = anchor_on_line(movement['corridor'], location)
        if anchor['distanceAlongLegMeters'] < previous + 5:
            raise ValueError('Checkpoints must be ordered and separated')
        previous = anchor['distanceAlongLegMeters']
        for key, endpoint in (('approach', -1), ('departure', 0)):
            path = points({'type': 'LineString', 'coordinates': checkpoint[key]})
            if len(path) < 2 or meters(path[0], path[-1]) < 8 or meters(path[endpoint], location) > .5:
                raise ValueError('Invalid checkpoint direction evidence')
            other = anchor_on_line(movement['corridor'], path[0 if key == 'approach' else -1])
            delta = other['distanceAlongLegMeters'] - anchor['distanceAlongLegMeters']
            if (key == 'approach' and delta > -8) or (key == 'departure' and delta < 8):
                raise ValueError('Checkpoint direction does not follow approved corridor')
    return sequence


def route_sequence(sequence, line, offset, route_distance, entry_distance, exit_distance):
    from copy import deepcopy
    result = deepcopy(sequence)
    result.pop('review', None)
    previous = entry_distance
    for checkpoint in result['checkpoints']:
        anchor = anchor_on_line(line, checkpoint.pop('location'), previous, exit_distance)
        previous = anchor['distanceAlongLegMeters'] + 5
        anchor['geometrySegmentIndex'] += offset
        anchor['distanceAlongRouteMeters'] = route_distance+anchor['distanceAlongLegMeters']
        checkpoint['anchor'] = anchor
        checkpoint['incomingBearing'] = bearing(checkpoint.pop('approach'))
        checkpoint['outgoingBearing'] = bearing(checkpoint.pop('departure'))
    return result
