"""Command line entry point.

spm harmonize                 download source cases, validate, write data/cases/cases.csv
spm evaluate                  score models with leave-one-out, write results/
spm evaluate --models ring --res 5     reproduce MapScore's 5 m cells (slow, ~25M cells per case)
spm osm-lines PBF             extract trails/roads/streams from an OSM extract (run once per region)
spm nhd-lines GPKG            extract streams from a USGS NHD state GeoPackage (run once per region)
spm fetch-dem LON_MIN LAT_MIN LON_MAX LAT_MAX           pre-download 3DEP tiles for offline use
spm region LON_MIN LAT_MIN LON_MAX LAT_MAX              prebuild the terrain for an operating area
spm holdout --source mapscore --frac 0.33 --seed N      freeze a test set (configs/holdout.yaml)
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from spm.cases.harmonize import harmonize, load_cases
from spm.cases.split import DEFAULT_PATH as HOLDOUT_PATH
from spm.cases.split import make_holdout, write_holdout
from spm.eval.runner import evaluate, summarize
from spm.features.spec import load_specs
from spm.models import REGISTRY, RingModel
from spm.models.bayes import BayesModel

ROOT = Path.cwd()


def _factories(names: list[str], quantiles_path: Path) -> dict:
    out = {}
    for n in names:
        if n == "ring_published":
            q = (yaml.safe_load(quantiles_path.read_text()) or {}).get("categories") or {}
            q = {k: v for k, v in q.items() if v and all(v.get(x) for x in ("q25", "q50", "q75"))}
            if not q:
                print(f"skipping ring_published: no complete entries in {quantiles_path}")
                continue
            out[n] = lambda q=q: _named(RingModel(quantiles=q), "ring_published")
        elif n == "bayes":
            specs = load_specs(ROOT / "configs" / "prior_art.yaml")
            out[n] = lambda specs=specs: BayesModel(specs)
        else:
            out[n] = REGISTRY[n]
    return out


def _builder(args, terrain: Path):
    """StackBuilder over every region's line files (needs the [geo] extras)."""
    from spm.geodata.build import StackBuilder

    line_files = args.lines or sorted(terrain.glob("osm_lines*.gpkg"))
    stream_files = args.streams
    if stream_files is None:
        stream_files = sorted(terrain.glob("nhd_lines*.gpkg"))
    print("lines:", ", ".join(p.name for p in line_files))
    print("streams:", ", ".join(p.name for p in stream_files) or "from the lines files")
    return StackBuilder(
        line_files,
        tile_dir=terrain / "dem_tiles",
        cache_dir=terrain / "stacks",
        streams_gpkg=stream_files or None,
    )


def _named(model, name):
    model.name = name
    return model


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="spm")
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    sub = ap.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("harmonize", help="download + validate source cases")
    h.add_argument("--no-download", action="store_true")

    e = sub.add_parser("evaluate", help="score models on harmonized cases")
    e.add_argument("--models", default="uniform,ring_pooled,ring")
    e.add_argument("--split", default="loo", choices=["loo", "loro"])
    e.add_argument("--res", type=float, default=25.0, help="cell size in metres (MapScore used 5)")
    e.add_argument("--quantiles", type=Path, default=ROOT / "configs" / "ring_quantiles.yaml")
    e.add_argument("--out", type=Path, default=ROOT / "results")

    o = sub.add_parser("osm-lines", help="extract trails/roads/streams from an OSM .pbf")
    o.add_argument("pbf", type=Path)
    o.add_argument("--out", type=Path, default=None, help="default: data/terrain/osm_lines.gpkg")

    nh = sub.add_parser("nhd-lines", help="extract streams from an unzipped NHD state GeoPackage")
    nh.add_argument("nhd", type=Path)
    nh.add_argument("--out", type=Path, default=None, help="default: data/terrain/nhd_lines.gpkg")
    nh.add_argument(
        "--exclude-fcode", type=int, nargs="*", default=[], help="e.g. 46007 ephemeral washes"
    )

    ho = sub.add_parser("holdout", help="draw and freeze the test set")
    ho.add_argument("--source", default="mapscore", help="cases of this source are split")
    ho.add_argument("--frac", type=float, default=1 / 3)
    ho.add_argument("--seed", type=int, required=True)
    ho.add_argument("--force", action="store_true", help="redraw an existing holdout")

    rg = sub.add_parser("region", help="prebuild the 10 m terrain stack for an operating area")
    rg.add_argument(
        "bbox", type=float, nargs=4, metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX")
    )
    rg.add_argument("--feature-res", type=float, default=10.0)
    rg.add_argument("--lines", type=Path, nargs="*", default=None)
    rg.add_argument("--streams", type=Path, nargs="*", default=None)

    fd = sub.add_parser("fetch-dem", help="download 3DEP tiles covering a lon/lat box")
    fd.add_argument(
        "bbox", type=float, nargs=4, metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX")
    )

    args = ap.parse_args(argv)
    terrain = args.data / "terrain"

    if args.cmd == "harmonize":
        df, issues = harmonize(args.data, download=not args.no_download)
        print(f"kept {len(df)} cases -> {args.data / 'cases' / 'cases.csv'}")
        if len(issues):
            print(issues.groupby(["action", "reason"]).size().rename("n").to_string())
        print("\ncases per category:\n" + df["category"].value_counts().to_string())

    elif args.cmd == "evaluate":
        cases = load_cases(args.data)
        per_case = evaluate(
            _factories(args.models.split(","), args.quantiles),
            cases,
            split=args.split,
            res=args.res,
        )
        summary = summarize(per_case)
        args.out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        per_case.to_csv(args.out / f"scores_{stamp}.csv", index=False)
        summary.to_csv(args.out / f"summary_{stamp}.csv", index=False)
        with pd.option_context("display.width", 120):
            print(summary.to_string(index=False))
        print(f"\nwritten to {args.out}/")

    elif args.cmd == "osm-lines":
        from spm.geodata import lines  # needs the [geo] extras

        out = args.out or terrain / "osm_lines.gpkg"
        n = lines.extract(args.pbf, out)
        print(f"wrote {n} lines -> {out}")

    elif args.cmd == "nhd-lines":
        from spm.geodata import lines  # needs the [geo] extras

        out = args.out or terrain / "nhd_lines.gpkg"
        n = lines.extract_nhd(args.nhd, out, tuple(args.exclude_fcode))
        print(f"wrote {n} stream lines -> {out}")

    elif args.cmd == "holdout":
        pool = [c for c in load_cases(args.data) if c.source == args.source and c.ipp]
        ids = make_holdout(pool, args.frac, args.seed)
        path = write_holdout(
            ROOT / HOLDOUT_PATH, ids, args.source, args.frac, args.seed, args.force
        )
        print(f"{len(ids)} of {len(pool)} {args.source} cases frozen as the test set -> {path}")

    elif args.cmd == "region":
        import time

        builder = _builder(args, terrain)
        t = time.time()
        stack = builder.region(tuple(args.bbox), args.feature_res)
        w = stack.window
        mb = sum(v.nbytes for v in stack.layers.values()) / 1e6
        print(
            f"region stack {w.n}x{w.n} at {w.res:g} m ({w.n * w.res / 1000:.1f} km), "
            f"{mb:.0f} MB in memory, built in {time.time() - t:.0f}s -> "
            f"{terrain / 'stacks' / 'regions'}/"
        )

    elif args.cmd == "fetch-dem":
        from spm.geodata import dem

        names = dem.tiles_for_bounds(*args.bbox)
        print(f"{len(names)} tiles -> {terrain / 'dem_tiles'}")
        for p in dem.fetch_tiles(names, terrain / "dem_tiles"):
            print(f"  {p.name} {p.stat().st_size / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
