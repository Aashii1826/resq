"""
Real-data loader using OSMnx / OpenStreetMap (Section 9, Mode A).

Not tied to any specific city - callers pass an area name or bbox.
If this fails for any reason (no internet, OSM outage, bad area name),
callers should catch the exception and fall back to synthetic_loader
(Section 35 - Fallback Strategy). We deliberately do NOT catch/hide
errors here so the caller can make that decision explicitly.
"""

from typing import Optional, Tuple

from app.config import ROAD_TYPE_CAPACITY, ROAD_TYPE_SPEED_KPH, CAPACITY_PER_EXTRA_LANE_MULTIPLIER
from app.models.asset import Asset, AssetType
from app.models.network import Network, RoadEdge


def _normalize_highway_tag(tag) -> str:
    """OSM 'highway' tag can be a string or a list; collapse to our known types."""
    if isinstance(tag, list):
        tag = tag[0]
    tag = str(tag)
    # fold link types (motorway_link etc) into their parent category
    for base in ROAD_TYPE_CAPACITY.keys():
        if tag.startswith(base):
            return base
    return "unclassified"


def _capacity_for(road_type: str, lanes: Optional[int]) -> float:
    base = ROAD_TYPE_CAPACITY.get(road_type, ROAD_TYPE_CAPACITY["unclassified"])
    if lanes and lanes > 1:
        base = base * (1 + (lanes - 1) * CAPACITY_PER_EXTRA_LANE_MULTIPLIER)
    return round(base, 1)


def load_area(area_name: str, hospital_query: Optional[str] = None) -> Network:
    """
    Load a small urban road network + hospitals for a named place
    (e.g. "Koramangala, Bengaluru, India"), via OSMnx.

    Requires network access to OpenStreetMap servers - not available in
    every environment. Prefer bounding-box loading (load_bbox) for tighter,
    faster pulls during a hackathon demo.
    """
    import osmnx as ox

    graph = ox.graph_from_place(area_name, network_type="drive", simplify=True)
    return _build_network_from_osmnx_graph(graph, source=f"osm:{area_name}", area_name=area_name)


def load_bbox(north: float, south: float, east: float, west: float) -> Network:
    """Load a road network within a bounding box via OSMnx."""
    import osmnx as ox

    graph = ox.graph_from_bbox(north, south, east, west, network_type="drive", simplify=True)
    return _build_network_from_osmnx_graph(graph, source="osm:bbox", area_name=None)


def _build_network_from_osmnx_graph(graph, source: str, area_name: Optional[str]) -> Network:
    import osmnx as ox

    net = Network()
    net.source = source

    for node_id, data in graph.nodes(data=True):
        net.add_junction(str(node_id), data["y"], data["x"])

    edge_counter = 0
    for u, v, data in graph.edges(data=True):
        edge_counter += 1
        road_type = _normalize_highway_tag(data.get("highway", "unclassified"))
        lanes = data.get("lanes")
        if isinstance(lanes, list):
            lanes = lanes[0]
        try:
            lanes = int(lanes) if lanes is not None else None
        except (TypeError, ValueError):
            lanes = None

        length = float(data.get("length", 100.0))
        speed = ROAD_TYPE_SPEED_KPH.get(road_type, 30)
        capacity = _capacity_for(road_type, lanes)

        geometry = None
        if "geometry" in data:
            geometry = [(lat, lon) for lon, lat in data["geometry"].coords]

        edge = RoadEdge(
            edge_id=f"R{edge_counter}",
            source=str(u),
            target=str(v),
            length=length,
            road_type=road_type,
            speed=speed,
            capacity=capacity,
            geometry=geometry,
            metadata={"osm_lanes": lanes},
        )
        net.add_road(edge)

    # hospitals via OSM amenity tags, best-effort
    try:
        if area_name:
            tags = {"amenity": "hospital"}
            hospitals_gdf = ox.features_from_place(area_name, tags)
        else:
            hospitals_gdf = None

        if hospitals_gdf is not None and len(hospitals_gdf) > 0:
            for i, (idx, row) in enumerate(hospitals_gdf.iterrows()):
                geom = row.geometry
                if geom is None:
                    continue
                centroid = geom.centroid
                lat, lon = centroid.y, centroid.x
                nearest_node = str(ox.distance.nearest_nodes(graph, lon, lat))
                hospital = Asset(
                    id=f"H{i+1}",
                    type=AssetType.HOSPITAL,
                    name=row.get("name", f"Hospital {i+1}") or f"Hospital {i+1}",
                    latitude=lat,
                    longitude=lon,
                    capacity=200,  # unknown from OSM -> documented assumption
                    metadata={"source": "osm_amenity_hospital"},
                )
                net.add_hospital(hospital, anchor_node=nearest_node)
    except Exception:
        # Hospitals are best-effort; a road network without hospital tags
        # is still usable. Caller can also merge synthetic hospitals in.
        pass

    net.refresh_weights()
    return net
