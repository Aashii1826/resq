"""
Unified data loading entrypoint (Section 35 - Fallback Strategy).

The simulation engine should never know or care whether a Network came
from OSM or from the synthetic generator - both produce the same
Network/RoadEdge/Asset shapes. This module is the ONLY place that
decides which source to use and handles the fallback.
"""

import logging
from typing import Optional

from app.data.synthetic_loader import build_synthetic_network
from app.models.network import Network

logger = logging.getLogger("resq.data.loader")


def load_network(
    mode: str = "demo",
    area_name: Optional[str] = None,
    bbox: Optional[tuple] = None,
) -> Network:
    """
    mode:
      "demo"      -> deterministic synthetic network (default, always works)
      "real"      -> OSM data via area_name or bbox, falls back to synthetic
                      on any failure so a demo never breaks (Section 35)
    """
    if mode == "real":
        try:
            from app.data import osm_loader

            if area_name:
                logger.info("Loading real network for area: %s", area_name)
                return osm_loader.load_area(area_name)
            elif bbox:
                north, south, east, west = bbox
                logger.info("Loading real network for bbox: %s", bbox)
                return osm_loader.load_bbox(north, south, east, west)
            else:
                raise ValueError("mode='real' requires area_name or bbox")
        except Exception as exc:  # noqa: BLE001 - intentional broad fallback
            logger.warning(
                "Real data load failed (%s). Falling back to synthetic demo network.",
                exc,
            )
            return build_synthetic_network()

    # default / "demo" mode
    return build_synthetic_network()
