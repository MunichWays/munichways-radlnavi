"""Resolve cycling attributes relative to OSM way order, shared with the Lua profile.

Keep routing/tests/cycling-attribute-cases.json passing in both languages.
This selects a modeled surface, never grants access or changes oneway rules.
"""

from dataclasses import dataclass


INFRASTRUCTURE = {
    "lane", "track", "shared_lane", "share_busway", "shared", "yes",
    "opposite", "opposite_lane", "opposite_track",
}
OPPOSITE = {"opposite", "opposite_lane", "opposite_track"}
EXCLUDED = {"no", "separate"}


@dataclass(frozen=True)
class CyclingAttribute:
    value: str | None = None
    source: str | None = None
    side: str | None = None
    conflict: bool = False
    ambiguous: bool = False


def resolve_cycling_attribute(tags, key, forward):
    """forward=None means that a repeated OSM edge has ambiguous way order.

    Generic surface:left/right describe physical halves, not necessarily cycling
    directions, and are deliberately not aliases here. Width has no cost model.
    """

    def value(name):
        return tags.get(name) or None

    def pair(side, attribute):
        return (f"cycleway:{side}:{attribute}", f"cycleway:{attribute}:{side}")

    if value("bicycle") == "dismount" and key != "width":
        return CyclingAttribute(value(key), key if value(key) else None)

    def has_attributes(side):
        # Width must not change the surface/smoothness selected for routing.
        attributes = ("surface", "smoothness")
        if key == "width":
            attributes += ("width",)
        return any(
            value(name) for attribute in attributes for name in pair(side, attribute)
        )

    left_driving = value("driving_side") == "left"
    preferred = "left" if (forward is True) == left_driving else "right"
    candidates = []
    scoped = False
    ambiguous = False
    conflict = False
    for side in ("right", "left"):
        infrastructure = (
            value(f"cycleway:{side}") or value("cycleway:both") or value("cycleway")
        )
        present = (
            infrastructure is not None or has_attributes(side) or has_attributes("both")
        )
        scoped = scoped or present
        if infrastructure in EXCLUDED:
            conflict = conflict or any(value(name) for name in pair(side, key))
            continue
        if not present:
            continue
        if infrastructure is not None and infrastructure not in INFRASTRUCTURE:
            ambiguous = True
            continue
        along = (side == "right") != left_driving
        road_oneway = value("oneway")
        if road_oneway in {"yes", "1", "true"}:
            along = True
        elif road_oneway == "-1":
            along = False
        if infrastructure in OPPOSITE:
            along = road_oneway == "-1"
        oneway = (
            value(f"cycleway:{side}:oneway")
            or value("cycleway:both:oneway")
            or value("cycleway:oneway")
        )
        if oneway in {"yes", "1", "true"}:
            along = True
        elif oneway == "-1":
            along = False
        elif oneway not in {None, "no", "0", "false"}:
            ambiguous = True
            continue
        if forward is None:
            ambiguous = True
        elif oneway in {"no", "0", "false"} or along == forward:
            candidates.append(side)

    side = preferred if preferred in candidates else next(iter(candidates), None)
    # A valid regular-side candidate wins over an uncertain other side. Without
    # it, do not silently choose a potentially unrelated opposite-side surface.
    if side != preferred and ambiguous:
        side = None
    if side is not None:
        ambiguous = False
        for scope in (side, "both"):
            canonical, alias = pair(scope, key)
            first, second = value(canonical), value(alias)
            conflict = bool(conflict or (first and second and first != second))
            if first or second:
                return CyclingAttribute(
                    first or second, canonical if first else alias, side, conflict
                )

    # Preserve #20's unsided cycleway override on paths without side topology.
    # If a direction has no cycleway (no/separate/wrong-way), use the road tag.
    common = f"cycleway:{key}"
    if (side is not None or not scoped or ambiguous) and value(common):
        return CyclingAttribute(value(common), common, side, bool(conflict), ambiguous)
    # A road's overall width is never a substitute for missing cycle-lane width.
    standalone = value("highway") in {"cycleway", "path", "footway", "track"}
    if key != "width" or (standalone and side is None and not scoped):
        return CyclingAttribute(
            value(key), key if value(key) else None, side, bool(conflict), ambiguous
        )
    return CyclingAttribute(side=side, conflict=bool(conflict), ambiguous=ambiguous)
