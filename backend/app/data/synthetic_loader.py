"""
Deterministic synthetic urban network generator.

Design goals (Section 9, Mode B):
  - resembles an urban road system, not a random graph
  - ~50-150 nodes, ~100-300 edges, 5-10 hospitals
  - deterministic: same seed -> identical graph every run (demo mode requirement)
  - has a genuine structural bottleneck (a "bridge") so criticality/cascade
    demos are compelling out of the box, instead of a flat, boring grid

Layout: two grid "districts" (west bank / east bank) joined by only a
handful of bridge roads, similar to a river-split city. That handful of
bridge edges is intentionally the highest-criticality asset in the demo.
"""

import random
from typing import Dict, List, Tuple

from app.config import DEMO_SEED, ROAD_TYPE_CAPACITY, ROAD_TYPE_SPEED_KPH
from app.models.asset import Asset, AssetType, PopulationZone
from app.models.network import Network, RoadEdge

# District grid dimensions (rows x cols), two districts -> total nodes:
ROWS = 8
COLS = 7  # 8*7 = 56 nodes per district -> 112 total (within 50-150 target)

NODE_SPACING_DEG = 0.004  # approx grid spacing in degrees (~400m)
BASE_LAT = 12.9716  # Bengaluru-ish, arbitrary anchor for a plausible map view
BASE_LON = 77.5946
DISTRICT_GAP_DEG = 0.01  # gap between west/east district representing the "river"

ARTERIAL_STRIDE = 3  # every Nth row/col is an arterial (higher capacity)


def _node_id(district: str, r: int, c: int) -> str:
    return f"{district}_{r}_{c}"


def _road_type_for(r: int, c: int, is_bridge: bool = False) -> str:
    if is_bridge:
        return "trunk"
    if r % ARTERIAL_STRIDE == 0 or c % ARTERIAL_STRIDE == 0:
        return "primary" if (r % ARTERIAL_STRIDE == 0 and c % ARTERIAL_STRIDE == 0) else "secondary"
    return "residential" if (r + c) % 2 == 0 else "tertiary"


def _capacity_for(road_type: str, rng: random.Random) -> float:
    base = ROAD_TYPE_CAPACITY[road_type]
    # +/-10% deterministic jitter so not every road of a type is identical
    jitter = rng.uniform(0.9, 1.1)
    return round(base * jitter, 1)


def _length_m(rng: random.Random) -> float:
    # city block length, ~300-450m with deterministic jitter
    return round(rng.uniform(300, 450), 1)


def build_synthetic_network(seed: int = DEMO_SEED) -> Network:
    rng = random.Random(seed)
    net = Network()
    net.source = "synthetic"

    edge_counter = 0

    def add_bidirectional_road(u: str, v: str, road_type: str, is_bridge: bool = False):
        nonlocal edge_counter
        (ulat, ulon) = net.node_coords(u)
        (vlat, vlon) = net.node_coords(v)
        length = _length_m(rng)
        speed = ROAD_TYPE_SPEED_KPH[road_type]
        for a, b in [(u, v), (v, u)]:
            edge_counter += 1
            eid = f"R{edge_counter}"
            cap = _capacity_for(road_type, rng)
            edge = RoadEdge(
                edge_id=eid,
                source=a,
                target=b,
                length=length,
                road_type=road_type,
                speed=speed,
                capacity=cap,
                geometry=[net.node_coords(a), net.node_coords(b)],
                metadata={"is_bridge": is_bridge},
            )
            net.add_road(edge)

    # ---- build two districts as grids -------------------------------------
    districts = {
        "west": (BASE_LON, 1),
        "east": (BASE_LON + COLS * NODE_SPACING_DEG + DISTRICT_GAP_DEG, 1),
    }

    for district, (origin_lon, _) in districts.items():
        for r in range(ROWS):
            for c in range(COLS):
                lat = BASE_LAT + r * NODE_SPACING_DEG
                lon = origin_lon + c * NODE_SPACING_DEG
                net.add_junction(_node_id(district, r, c), lat, lon)

        # horizontal roads (along a row)
        for r in range(ROWS):
            for c in range(COLS - 1):
                u, v = _node_id(district, r, c), _node_id(district, r, c + 1)
                rtype = _road_type_for(r, c)
                add_bidirectional_road(u, v, rtype)

        # vertical roads (along a column)
        for c in range(COLS):
            for r in range(ROWS - 1):
                u, v = _node_id(district, r, c), _node_id(district, r + 1, c)
                rtype = _road_type_for(r, c)
                add_bidirectional_road(u, v, rtype)

    # ---- bridges connecting the two districts (the deliberate bottleneck) --
    # Only 3 bridge roads (6 directed edges) connect ~112 nodes worth of city.
    bridge_rows = [1, ROWS // 2, ROWS - 2]
    for r in bridge_rows:
        u = _node_id("west", r, COLS - 1)
        v = _node_id("east", r, 0)
        add_bidirectional_road(u, v, "trunk", is_bridge=True)

    # ---- hospitals (8) spread across both districts, incl. one that is
    #      only reachable (efficiently) via the bridges -----------------------
    hospital_specs = [
        ("H1", "west", 1, 1),
        ("H2", "west", 5, 2),
        ("H3", "west", 3, 5),  # near the bridge on the west side
        ("H4", "east", 1, 1),
        ("H5", "east", 5, 2),
        ("H6", "east", 6, 5),
        ("H7", "west", 6, 0),
        ("H8", "east", 2, 6),
    ]
    for hid, district, r, c in hospital_specs:
        anchor = _node_id(district, r, c)
        lat, lon = net.node_coords(anchor)
        hospital = Asset(
            id=hid,
            type=AssetType.HOSPITAL,
            name=f"Hospital {hid}",
            latitude=lat,
            longitude=lon,
            capacity=rng.choice([150, 200, 250, 300]),
            baseline_load=0.0,
            current_load=0.0,
        )
        net.add_hospital(hospital, anchor_node=anchor)

    # ---- population zones (~18), anchored to grid nodes, varied population --
    zone_count = 18
    zone_id = 0
    # only real routable junctions - exclude the decorative hospital:* nodes
    junction_nodes = [
        n for n, data in net.graph.nodes(data=True) if data.get("node_type") == "JUNCTION"
    ]
    rng.shuffle(junction_nodes)
    for anchor in junction_nodes[:zone_count]:
        zone_id += 1
        lat, lon = net.node_coords(anchor)
        population = rng.randint(2000, 12000)
        zone = PopulationZone(
            zone_id=f"zone_{zone_id}",
            latitude=lat,
            longitude=lon,
            population=population,
            anchor_node=anchor,
        )
        net.add_zone(zone)

    net.refresh_weights()
    return net


if __name__ == "__main__":
    net = build_synthetic_network()
    print(net.summary())
