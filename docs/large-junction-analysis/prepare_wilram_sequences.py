"""Prepare reviewed Wilram sequences from frozen routes; no runtime writes."""
from copy import deepcopy
import json

from verify_review_updates import ROOT, FIXTURES, read, write
from src.big_junctions import crossings, meters, point_at, validate_catalog, add_guidance
from src.junction_sequences import anchor_on_line
from unittest.mock import patch

OUTPUT = ROOT / 'review-wilram-sequences-proposed-catalog.json'
CONTRACTS = ROOT.parents[1] / 'backend/tests/fixtures/big-junctions/wilram-sequences'


def prepare():
    proposed = read(ROOT / 'review-updates-2026-11-14-proposed-catalog.json')
    proposed['version'] = 'munich-big-junctions-sequences-proposed'
    junction = next(j for j in proposed['junctions'] if j['id'] == 'thomasiusplatz')
    # Preserve the eight existing public movement IDs across the geometry update.
    for movement in junction['movements']:
        movement['id'] = '-'.join(movement['id'].split('-')[:3])
    report = next(j for j in read(ROOT / 'review-updates-2026-11-14-routes.json')['junctions'] if j['number'] == 10)
    english = {
        ('Entry-3', 'Exit-5'): 'continue straight at the large junction, then immediately right, then left into Wilramstraße',
        ('Entry-4', 'Exit-5'): 'turn left at the large junction, then immediately right, then left into Wilramstraße',
        ('Entry-5', 'Exit-1'): 'turn right, then continue straight at the large junction',
        ('Entry-5', 'Exit-4'): 'turn right, then turn left at the large junction',
        ('Entry-5', 'Exit-3'): 'turn right, then make a U-turn at the large junction',
    }
    raw = {}
    for item in report['movements']:
        if item['kind'] != 'special':
            continue
        if not item.get('geometryVerified'):
            raise ValueError('Unverified special path')
        payload = read(FIXTURES / item['fixture'])
        line = payload['routes'][0]['geometry']['coordinates']
        entry, exit = crossings(line, junction['polygon']['coordinates'][0])
        start, end = entry['geometrySegmentIndex'], exit['geometrySegmentIndex']
        movement = ('uturn' if item['exitLabel'] == 'Exit-3' else 'left'
                    if item['entryLabel'] == 'Entry-4' or item['exitLabel'] == 'Exit-4' else 'straight')
        checkpoints = []
        requested = ([([11.602406, 48.115690], 'right'), ([11.602413, 48.115448], 'left')]
                     if item['exitLabel'] == 'Exit-5' else [([11.602413, 48.115448], 'right')])
        for index, (location, turn) in enumerate(requested):
            at = anchor_on_line(line, location)['distanceAlongLegMeters']
            text = {'de': 'Hier rechts.' if turn == 'right' else 'Hier links in Wilramstraße.',
                    'en': 'Turn right here.' if turn == 'right' else 'Turn left here into Wilramstraße.'}
            checkpoint = dict(id=f'turn-{index+1}', location=location, instruction=text, modifier=turn,
                approach=[point_at(line, at-15), location], departure=[location, point_at(line, at+15)])
            if item['entryLabel'] == 'Entry-4' and index == 0:
                checkpoint['alignedInstruction'] = {'de': 'Hier geradeaus.', 'en': 'Continue straight here.'}
            checkpoints.append(checkpoint)
        advance = item['requestedGuidance']['advance'].rstrip('.')
        advance = advance[0].lower()+advance[1:]
        direction = {'left': ('links', 'left'), 'straight': ('geradeaus', 'straight'), 'uturn': ('wenden', 'U-turn')}[movement]
        display = ({'de': f'große Kreuzung {direction[0]}', 'en': f'large junction {direction[1]}'}
                   if item['exitLabel'] == 'Exit-5' else
                   {'de': f'rechts, dann Kreuzung {direction[0]}', 'en': f'right, then junction {direction[1]}'})
        sequence = dict(version=1, advance={'de': advance, 'en': english[(item['entryLabel'], item['exitLabel'])]},
            display=display, checkpoints=checkpoints,
            review={'status': 'approved', 'date': '2026-11-14',
                    'evidence': 'Thomas requested these six Wilram cases and approved K10 v4. Direction-confirmed aligned instruction is limited to the first Entry-4 outbound checkpoint.'})
        junction['movements'].append(dict(id=item['id'], enabled=True, movement=movement,
            entryArm='wilram' if item['entryLabel'] == 'Entry-5' else 'north' if item['entryLabel'] == 'Entry-4' else 'west',
            exitArm={'Exit-1': 'north', 'Exit-3': 'south', 'Exit-4': 'west', 'Exit-5': 'wilram'}[item['exitLabel']],
            entry=entry['location'], exit=exit['location'],
            corridor=[entry['location'], *line[start+1:end+1], exit['location']],
            approach=[point_at(line, entry['distanceAlongLegMeters']-15), entry['location']],
            departure=[exit['location'], point_at(line, exit['distanceAlongLegMeters']+15)],
            sequence=sequence, review=deepcopy(sequence['review'])))
        raw[item['id']] = payload
    validate_catalog(proposed)
    CONTRACTS.mkdir(exist_ok=True)
    with patch('src.big_junctions.catalog', return_value=proposed):
        for identifier, payload in raw.items():
            enriched = add_guidance(payload, sequence_guidance=True)
            if enriched is None or add_guidance(payload) is not None:
                raise ValueError('Sequence missing or emitted to legacy client: '+identifier)
            restored = deepcopy(enriched)
            restored['routes'][0].pop('guidance')
            if restored != payload:
                raise ValueError('Raw route changed')
            write(CONTRACTS / f'{identifier}.json', enriched)
    write(OUTPUT, proposed)
    print('Prepared five sequence contracts; runtime unchanged.')
    return proposed


if __name__ == '__main__':
    prepare()
