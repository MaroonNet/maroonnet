"""Search sectors from the mission database, as the GeoJSON `spm update` reads.

`spm update` re-weights a probability map after ground has been searched without a find. It
takes sector polygons, each with a "pod" property: the probability of detection, 0 to 1, that
the search would have found the subject had they been there.

The mission database holds no POD yet, so the caller supplies it: one value for every sector,
values for single sectors, or both. A sector left without a POD is written without the
property, and spm reports it as ignored instead of guessing.

    cd backend
    uv run python -m mapdb.sectors --pod 0.5 --out searched.geojson
    uv run python -m mapdb.sectors --pod-for 3=0.8 --pod-for 4=0.4 --out searched.geojson

Only completed sectors are exported unless --status says otherwise. The database is the one
MISSIONDB_URL names (missiondb/db.py).
"""

import argparse
import json
from pathlib import Path

from sqlmodel import Session, select

from missiondb import get_engine
from missiondb.models import SearchSector, SearchSectorPoint, SectorStatus


def sectors_geojson(
    session: Session,
    pod: float | None = None,
    pod_by_sector: dict[int, float] | None = None,
    statuses: tuple[SectorStatus, ...] = (SectorStatus.COMPLETED,),
) -> dict:
    """A FeatureCollection with one polygon per sector whose status is in statuses.

    pod applies to every sector; pod_by_sector (sector id: POD) overrides it for single ones.
    """
    pod_by_sector = pod_by_sector or {}
    for value in (pod, *pod_by_sector.values()):
        if value is not None and not 0 <= value <= 1:
            raise ValueError(f"a POD is between 0 and 1, not {value}")

    features = []
    sectors = session.exec(
        select(SearchSector)
        .where(SearchSector.status.in_(statuses))
        .order_by(SearchSector.search_sector_id)
    ).all()
    for sector in sectors:
        points = session.exec(
            select(SearchSectorPoint)
            .where(SearchSectorPoint.search_sector_id == sector.search_sector_id)
            .order_by(SearchSectorPoint.point_order)
        ).all()
        if len(points) < 3:  # not a polygon; the database cannot enforce the three-point rule
            continue
        ring = [[point.lon, point.lat] for point in points]
        ring.append(ring[0])  # GeoJSON closes a polygon by repeating its first point
        properties = {"id": sector.search_sector_id, "status": sector.status.value}
        sector_pod = pod_by_sector.get(sector.search_sector_id, pod)
        if sector_pod is not None:
            properties["pod"] = sector_pod
        features.append({
            "type": "Feature",
            "id": sector.search_sector_id,
            "properties": properties,
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        })
    return {"type": "FeatureCollection", "features": features}


def _sector_pod(text: str) -> tuple[int, float]:
    """'3=0.8' as (3, 0.8)."""
    sector_id, _, value = text.partition("=")
    return int(sector_id), float(value)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="export searched sectors for `spm update`")
    parser.add_argument("--pod", type=float, default=None, help="POD for every sector, 0 to 1")
    parser.add_argument("--pod-for", type=_sector_pod, action="append", default=[],
                        metavar="SECTOR_ID=POD", help="POD for one sector; may be repeated")
    parser.add_argument("--status", action="append", default=None,
                        choices=[status.value for status in SectorStatus],
                        help="which sectors to export; default: completed")
    parser.add_argument("--out", type=Path, required=True, help="the GeoJSON file to write")
    args = parser.parse_args(argv)

    statuses = tuple(SectorStatus(value) for value in args.status or ["completed"])
    with Session(get_engine()) as session:
        collection = sectors_geojson(session, args.pod, dict(args.pod_for), statuses)
    args.out.write_text(json.dumps(collection, indent=2) + "\n")
    with_pod = sum("pod" in feature["properties"] for feature in collection["features"])
    print(f"{len(collection['features'])} sectors written to {args.out}, {with_pod} with a POD")


if __name__ == "__main__":
    main()
