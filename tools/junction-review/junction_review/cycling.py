"""Shared OSM bicycle access and direction rules."""


def direction(tags):
    if tags.get('highway') not in {'cycleway','path','footway','pedestrian','residential','unclassified','living_street','service',
                                   'primary','secondary','tertiary','primary_link','secondary_link','tertiary_link','road','track'}:
        return []
    if tags.get('bicycle') in ('no', 'private', 'use_sidepath') or tags.get('access') in ('no', 'private') and tags.get('bicycle') not in ('yes', 'designated', 'permissive'):
        return []
    if tags.get('highway') in ('motorway', 'motorway_link', 'trunk', 'trunk_link', 'steps'):
        return []
    if tags.get('highway') in ('footway', 'pedestrian', 'path') and tags.get('bicycle') not in ('yes', 'designated', 'permissive'):
        return []
    one = tags.get('oneway:bicycle', tags.get('oneway', 'yes' if tags.get('junction') == 'roundabout' else 'no'))
    if 'oneway:bicycle' not in tags and any(v in ('opposite', 'opposite_lane', 'opposite_track') for k, v in tags.items() if k.startswith('cycleway')):
        one = 'no'
    if 'oneway:bicycle' not in tags and any(tags.get(f'cycleway:{side}:oneway') == '-1' for side in ('left', 'right', 'both')):
        one = 'no'
    allowed = [-1] if one == '-1' else [1] if one in ('yes', '1', 'true') else [1, -1]
    return [sign for sign in allowed if tags.get('bicycle:forward' if sign == 1 else 'bicycle:backward') != 'no']
