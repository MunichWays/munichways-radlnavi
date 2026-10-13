"""Bounded, pedestrian-only endpoint connections; never changes the bike graph.

The regional dataset is German. On public pedestrian ways bicycle=no forbids
riding; foot access can supply a pushing connection. Explicit pushing/physical
prohibitions, private access, closed barriers and conditional access are excluded.
"""

from dataclasses import dataclass
from heapq import heappop, heappush
from json import loads
from math import asin, atan2, cos, degrees, radians, sin, sqrt


MAX_ACCESS_METERS = 500
MAX_SNAP_METERS = 20
MAX_WAYS = 2000
MAX_NODES = 20000
MAX_CONNECTIONS = 64
DENIED = {"no", "private", "agricultural", "forestry", "delivery"}
PUBLIC = {"yes", "designated", "permissive"}
PEDESTRIAN = {"footway", "pedestrian", "steps"}
CYCLING = {
    "cycleway", "path", "track", "primary", "primary_link", "secondary",
    "secondary_link", "tertiary", "tertiary_link", "residential", "service",
    "living_street", "road", "unclassified",
}
PASSABLE_BARRIERS = {"no", "gate", "lift_gate", "entrance", "bollard",
                     "cycle_barrier", "kerb", "block", "cattle_grid"}


def meters(a, b):
    x, y = radians(b[1] - a[1]), radians(b[0] - a[0])
    value = sin(x / 2) ** 2 + cos(radians(a[1])) * cos(radians(b[1])) * sin(y / 2) ** 2
    return 12742017.6 * asin(min(1, sqrt(value)))


def bearing(a, b):
    lon = radians(b[0] - a[0])
    return round(degrees(atan2(sin(lon) * cos(radians(b[1])),
        cos(radians(a[1])) * sin(radians(b[1])) -
        sin(radians(a[1])) * cos(radians(b[1])) * cos(lon)))) % 360


def conditional(tags):
    return any(tags.get(key) for key in (
        "access:conditional", "foot:conditional", "bicycle:conditional",
        "bicycle:pushing:conditional",
    ))


def pedestrian_access(tags):
    access = tags.get("foot", tags.get("access"))
    pushing = tags.get("bicycle:pushing")
    return (access is None or access in PUBLIC) and (pushing is None or pushing in PUBLIC)


def walkable(tags):
    highway = tags.get("highway")
    if highway not in PEDESTRIAN | {"path"} or conditional(tags):
        return False
    if tags.get("route") == "ferry" or tags.get("status") == "impassable":
        return False
    if not pedestrian_access(tags) or tags.get("bicycle:physical") == "no":
        return False
    if tags.get("bicycle") in {"private", "use_sidepath"}:
        return False
    # A path otherwise belongs to the bicycle graph. Do not create walking
    # shortcuts along rideable roads or cycling one-ways.
    return tags.get("bicycle") in {"no", "dismount"} or (
        highway in PEDESTRIAN and tags.get("bicycle") not in PUBLIC
    )


def rideable(tags):
    return (
        (tags.get("highway") in CYCLING or
         tags.get("highway") in {"footway", "pedestrian"} and tags.get("bicycle") in PUBLIC)
        and tags.get("bicycle", tags.get("vehicle", tags.get("access")))
            not in DENIED | {"dismount", "use_sidepath"}
        and tags.get("route") != "ferry"
        and tags.get("motorroad") != "yes"
        and not conditional(tags)
    )


def passable(tags):
    return (
        pedestrian_access(tags)
        and tags.get("bicycle:physical") != "no"
        # bicycle=no on a barrier can describe physical bicycle passage,
        # rather than just riding. Require explicit pushing permission there.
        and not (tags.get("barrier") and tags.get("bicycle") == "no"
                 and tags.get("bicycle:pushing") not in PUBLIC)
        # A locked vehicle gate can explicitly retain pedestrian access.
        and (tags.get("locked") != "yes" or tags.get("foot") in PUBLIC)
        and tags.get("barrier", "no") in PASSABLE_BARRIERS
        and not conditional(tags)
        and tags.get("opening_hours", "24/7") == "24/7"
    )


@dataclass(frozen=True)
class Node:
    coord: tuple
    tags: dict


@dataclass(frozen=True)
class Edge:
    a: int
    b: int
    distance: float
    speed: float
    name: str


@dataclass(frozen=True)
class Connection:
    coordinates: tuple
    nodes: tuple
    edges: tuple
    snap_distance: float

    @property
    def distance(self):
        return sum(edge.distance for edge in self.edges)

    @property
    def duration(self):
        return sum(edge.distance / (edge.speed / 3.6) for edge in self.edges)

    def reverse(self):
        return Connection(tuple(reversed(self.coordinates)), tuple(reversed(self.nodes)),
            tuple(Edge(e.b, e.a, e.distance, e.speed, e.name)
                  for e in reversed(self.edges)), self.snap_distance)


def batches(values):
    values = list(values)
    for i in range(0, len(values), 400):
        yield values[i:i + 400]


def box(point, radius):
    delta_lat = radius / 111000
    delta_lon = delta_lat / max(0.1, cos(radians(point[1])))
    return point[0] - delta_lon, point[0] + delta_lon, point[1] - delta_lat, point[1] + delta_lat


class AccessGraph:
    def __init__(self, db, point, radius):
        self.nodes, self.ways, self.edges, self.exits = {}, {}, {}, set()
        self.cycling_ways = {}
        if db is None or not db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='access_way_bounds'"
        ).fetchone():
            return
        bounds = box(point, radius)
        rows = db.execute(
            "SELECT w.id, w.node_list, w.tags FROM access_way_bounds b "
            "JOIN ways w ON w.id=b.id WHERE "
            "b.max_lon>=? AND b.min_lon<=? AND b.max_lat>=? AND b.min_lat<=? LIMIT ?",
            (*bounds, MAX_WAYS + 1),
        ).fetchall()
        if len(rows) > MAX_WAYS:
            return
        for way_id, refs, tags in rows:
            tags = loads(tags)
            if walkable(tags):
                self.ways[way_id] = (loads(refs), tags)
            elif rideable(tags):
                self.cycling_ways[way_id] = loads(refs)
        walking_nodes = {n for refs, _ in self.ways.values() for n in refs}
        node_ids = walking_nodes | {n for refs in self.cycling_ways.values() for n in refs}
        if len(node_ids) > MAX_NODES:
            self.ways = {}
            self.cycling_ways = {}
            return
        for batch in batches(node_ids):
            for i, lat, lon, tags in db.execute(
                f"SELECT id, lat, lon, tags FROM nodes WHERE id IN ({','.join('?' for _ in batch)})", batch
            ):
                self.nodes[i] = Node((lon, lat), loads(tags))
        for refs, tags in self.ways.values():
            speed = 2 if tags.get("highway") == "steps" else 4
            direction = tags.get("oneway:foot")
            for a, b in zip(refs, refs[1:]):
                if a not in self.nodes or b not in self.nodes:
                    continue
                if not passable(self.nodes[a].tags) or not passable(self.nodes[b].tags):
                    continue
                length = meters(self.nodes[a].coord, self.nodes[b].coord)
                if direction != "-1" and tags.get("foot:forward") in PUBLIC | {None}:
                    self.edges.setdefault(a, []).append(Edge(a, b, length, speed, tags.get("name", "")))
                if direction not in {"yes", "1", "true"} and tags.get("foot:backward") in PUBLIC | {None}:
                    self.edges.setdefault(b, []).append(Edge(b, a, length, speed, tags.get("name", "")))
        for refs in self.cycling_ways.values():
            self.exits.update(walking_nodes.intersection(refs))

    def cycling_gap(self, point):
        gap = float('inf')
        for refs in self.cycling_ways.values():
            for a, b in zip(refs, refs[1:]):
                if a in self.nodes and b in self.nodes:
                    gap = min(gap, self.projection(point, self.nodes[a].coord, self.nodes[b].coord)[0])
        return gap

    @staticmethod
    def projection(point, a, b):
        scale = cos(radians(point[1]))
        ax, ay = (a[0] - point[0]) * scale, a[1] - point[1]
        dx, dy = (b[0] - a[0]) * scale, b[1] - a[1]
        t = max(0, min(1, -(ax * dx + ay * dy) / (dx * dx + dy * dy))) if dx or dy else 0
        projected = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
        return meters(point, projected), projected

    def nearest(self, point):
        best = None
        for edges in self.edges.values():
            for edge in edges:
                a, b = self.nodes[edge.a].coord, self.nodes[edge.b].coord
                gap, projected = self.projection(point, a, b)
                if gap <= MAX_SNAP_METERS and (best is None or gap < best[0]):
                    best = gap, projected, edge
        return best

    def connections(self, point, *, incoming=False):
        nearest = self.nearest(point)
        if nearest is None:
            return []
        gap, projected, segment = nearest
        adjacency = self.edges
        if incoming:
            adjacency = {}
            for edges in self.edges.values():
                for edge in edges:
                    adjacency.setdefault(edge.b, []).append(
                        Edge(edge.b, edge.a, edge.distance, edge.speed, edge.name))
        queue, previous, best, lengths = [], {}, {}, {}
        # Seed only directions that exist on this mapped pedestrian segment.
        for a, b in ((segment.a, segment.b), (segment.b, segment.a)):
            for edge in adjacency.get(a, ()):
                if edge.b != b:
                    continue
                length = meters(projected, self.nodes[b].coord)
                if length > MAX_ACCESS_METERS:
                    continue
                partial = Edge(a, b, length, edge.speed, edge.name)
                cost = length / (edge.speed / 3.6)
                if cost < best.get(b, float('inf')):
                    best[b] = cost
                    lengths[b] = length
                    previous[b] = (None, partial)
                    heappush(queue, (cost, b))
        result = []
        while queue:
            cost, node_id = heappop(queue)
            if cost != best[node_id]:
                continue
            if node_id in self.exits:
                # Store predecessor edges, not a copy of the whole path for
                # every visited node. Dense indoor/park maps stay bounded.
                edges, cursor = [], node_id
                while cursor is not None:
                    cursor, edge = previous[cursor]
                    edges.append(edge)
                edges.reverse()
                refs = (edges[0].a,) + tuple(e.b for e in edges)
                coords = (projected,) + tuple(self.nodes[e.b].coord for e in edges)
                connection = Connection(coords, refs, tuple(edges), gap)
                result.append(connection.reverse() if incoming else connection)
                if len(result) >= MAX_CONNECTIONS:
                    break
            for edge in adjacency.get(node_id, ()):
                next_cost = cost + edge.distance / (edge.speed / 3.6)
                next_length = lengths[node_id] + edge.distance
                if next_length <= MAX_ACCESS_METERS and next_cost < best.get(edge.b, float('inf')):
                    best[edge.b] = next_cost
                    lengths[edge.b] = next_length
                    previous[edge.b] = (node_id, edge)
                    heappush(queue, (next_cost, edge.b))
        return result

    def walking_route(self, start, end):
        """Only walking edges, for two endpoints in the same pedestrian network."""
        destination = self.nearest(end)
        if destination is None:
            return None
        _, _, segment = destination
        previous = self.exits
        self.exits = {segment.a, segment.b}
        try:
            candidates = self.connections(start)
        finally:
            self.exits = previous
        gap, projected, segment = destination
        result = []
        for connection in candidates:
            node_id = connection.nodes[-1]
            for edge in self.edges.get(node_id, ()):
                if {edge.a, edge.b} != {segment.a, segment.b}:
                    continue
                partial = Edge(edge.a, edge.b, meters(self.nodes[node_id].coord, projected), edge.speed, edge.name)
                candidate = Connection(connection.coordinates + (projected,),
                    connection.nodes + (edge.b,), connection.edges + (partial,), connection.snap_distance)
                if candidate.distance <= MAX_ACCESS_METERS:
                    result.append(candidate)
        # Same edge: the shortest route need not first visit a bounding node.
        origin = self.nearest(start)
        if origin is not None and {origin[2].a, origin[2].b} == {segment.a, segment.b}:
            a, b = self.nodes[segment.a].coord, self.nodes[segment.b].coord
            forward = meters(a, origin[1]) <= meters(a, projected)
            node_a, node_b = (segment.a, segment.b) if forward else (segment.b, segment.a)
            edge = next((e for e in self.edges.get(node_a, ()) if e.b == node_b), None)
            if edge:
                result.append(Connection((origin[1], projected), (node_a, node_b),
                    (Edge(node_a, node_b, meters(origin[1], projected), edge.speed, edge.name),), origin[0]))
        return min(result, key=lambda c:c.duration) if result else None
