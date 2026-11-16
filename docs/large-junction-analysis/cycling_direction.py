"""Resolve bicycle direction on reviewed OSM ways without changing source tags."""


def bicycle_direction(tags):
    if 'oneway:bicycle' in tags:
        return tags['oneway:bicycle']
    # On a separately mapped shared path this concerns bicycles, not walkers.
    # On a carriageway cycleway:oneway does not define its vehicle direction.
    if tags.get('highway') in {'cycleway', 'path', 'footway'} and 'cycleway:oneway' in tags:
        return tags['cycleway:oneway']
    return tags.get('oneway', 'no')
