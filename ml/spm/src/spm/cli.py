"""Command line entry point.

spm harmonize                 download source cases, validate, write data/cases/cases.csv
spm evaluate                  score models with leave-one-out, write results/
spm evaluate --models ring --res 5     reproduce MapScore's 5 m cells (slow, ~25M cells per case)
spm osm-lines PBF             extract trails/roads/streams from an OSM extract (run once per region)
spm nhd-lines GPKG            extract streams from a USGS NHD state GeoPackage (run once per region)
spm stacks --source nysdec    build and cache terrain stacks around each case
spm evaluate-terrain          leave-one-region-out terrain models on find-only cases (NYS DEC)
spm gate-b                    Model B (terrain from NY finds) vs the ring on Arizona
spm fetch-dem LON_MIN LAT_MIN LON_MAX LAT_MAX           pre-download 3DEP tiles for offline use
spm region LON_MIN LAT_MIN LON_MAX LAT_MAX              prebuild the terrain for an operating area
spm holdout --source mapscore --frac 0.33 --seed N      freeze a test set (configs/holdout.yaml)
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from spm.cases.harmonize import harmonize, load_cases
from spm.cases.split import DEFAULT_PATH as HOLDOUT_PATH
from spm.cases.split import load_holdout, make_holdout, partition, write_holdout
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

    s = sub.add_parser("stacks", help="build + cache the terrain stacks HybridModel will request")
    s.add_argument("--source", default=None, help="only cases from this adapter")
    s.add_argument("--lines", type=Path, nargs="*", default=None, help="default: osm_lines*.gpkg")
    s.add_argument("--streams", type=Path, nargs="*", default=None, help="default: nhd_lines*.gpkg")
    s.add_argument("--res", type=float, default=100.0, help="model cell size, metres")
    s.add_argument("--feature-res", default="10", help="sub-cell feature size, metres, or none")
    s.add_argument("--side", type=float, default=25_000.0, help="IPP window side, metres")
    s.add_argument("--radius", type=float, default=1000.0, help="find disc radius (find-only)")
    s.add_argument("--limit", type=int, default=None, help="build at most this many")

    et = sub.add_parser("evaluate-terrain", help="region holdout on find-only cases")
    et.add_argument("--source", default="nysdec")
    et.add_argument("--situation", default="Lost", help="NYS DEC situation; 'all' for every one")
    et.add_argument("--feature-res", default="none,10", help="models to compare, e.g. none,10")
    et.add_argument("--radius", type=float, default=1000.0, help="find disc radius, metres")
    et.add_argument("--lines", type=Path, nargs="*", default=None, help="default: osm_lines*.gpkg")
    et.add_argument("--streams", type=Path, nargs="*", default=None, help="default: nhd_lines*")
    et.add_argument("--out", type=Path, default=ROOT / "results")

    g = sub.add_parser("gate-b", help="terrain weights from one source, scored on another")
    g.add_argument("--train-source", default="nysdec")
    g.add_argument("--train-situation", default="Lost")
    g.add_argument("--test-source", default="mapscore")
    g.add_argument("--res", type=float, default=100.0, help="model and scoring cell size")
    g.add_argument("--feature-res", type=float, default=10.0)
    g.add_argument("--radius", type=float, default=1000.0, help="find disc radius for training")
    g.add_argument(
        "--drop", nargs="*", default=[], metavar="FEATURE", help="leave these features out of B"
    )
    g.add_argument("--lam-w", type=float, default=1.0, help="L2 pull of weights toward prior")
    g.add_argument(
        "--lam-region",
        type=float,
        default=300.0,
        help="L2 pull of region corrections toward 0 (300: 5-fold CV on the 71 AZ "
        "training cases, 2026-11-05; the Arizona cases help through the shared weights)",
    )
    g.add_argument("--lines", type=Path, nargs="*", default=None, help="default: osm_lines*")
    g.add_argument("--streams", type=Path, nargs="*", default=None, help="default: nhd_lines*")
    g.add_argument("--out", type=Path, default=ROOT / "results")

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

    elif args.cmd == "stacks":
        from spm.models.hybrid import HybridModel

        builder = _builder(args, terrain)
        fr = None if args.feature_res.strip().lower() == "none" else float(args.feature_res)
        shape = HybridModel(
            [], builder, side_m=args.side, res=args.res, find_radius_m=args.radius, feature_res=fr
        )
        cases = [c for c in load_cases(args.data) if args.source in (None, c.source)]
        built = 0
        for c in cases[: args.limit]:
            window = shape.stack_window(c)
            if window is None:
                continue
            stack = builder(c, window)
            dem_ok = float(np.isfinite(stack["dem"]).mean())
            print(
                f"{c.case_id}: {window.n}x{window.n} at {window.res:g} m, dem {dem_ok:.0%}, "
                + ", ".join(f"{k} {int(stack[k].sum())}" for k in stack.layers if k != "dem")
            )
            built += 1
        print(f"\n{built} stacks in {terrain / 'stacks'}/")

    elif args.cmd == "evaluate-terrain":
        from spm.eval.find_only import by_region, leave_one_region_out, paired_summary
        from spm.models.hybrid import HybridModel

        builder = _builder(args, terrain)
        specs = load_specs(ROOT / "configs" / "prior_art.yaml")
        cases = [
            c
            for c in load_cases(args.data)
            if c.source == args.source
            and c.ipp is None
            and args.situation in ("all", c.extra.get("situation"))
        ]
        models = {}
        for fr in args.feature_res.split(","):
            feature_res = None if fr.strip().lower() == "none" else float(fr)
            name = "hybrid" if feature_res is None else f"hybrid_{feature_res:g}m"
            models[name] = lambda feature_res=feature_res: HybridModel(
                specs, builder, find_radius_m=args.radius, feature_res=feature_res
            )
        print(f"{len(cases)} find-only cases")
        per_case = leave_one_region_out(models, cases)
        summary = paired_summary(per_case)
        regions = by_region(per_case)
        args.out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        per_case.to_csv(args.out / f"terrain_scores_{stamp}.csv", index=False)
        summary.to_csv(args.out / f"terrain_summary_{stamp}.csv", index=False)
        with pd.option_context("display.width", 140):
            print(summary.to_string(index=False))
            print("\nmean log-lik gain over uniform, by held-out region:")
            print(regions.to_string())
        print(f"\nwritten to {args.out}/")

    elif args.cmd == "gate-b":
        from spm.eval.runner import paired
        from spm.features import aggregate
        from spm.models.hybrid import HybridModel

        builder = _builder(args, terrain)
        specs = load_specs(ROOT / "configs" / "prior_art.yaml")
        filled = ", ".join(s.name for s in specs if s.prior_complete and s.published)
        print(f"Model A (published features only): {filled or 'none'}")
        held_ids = load_holdout(ROOT / HOLDOUT_PATH)
        cases, held = partition(load_cases(args.data), held_ids)
        train = [
            c
            for c in cases
            if c.source == args.train_source
            and c.ipp is None
            and args.train_situation in ("all", c.extra.get("situation"))
        ]
        ipp_train = [c for c in cases if c.source == args.test_source and c.ipp is not None]
        if held:
            test = [c for c in held if c.source == args.test_source and c.ipp is not None]
            print(
                f"frozen test set: {len(test)} {args.test_source} cases; "
                f"{len(ipp_train)} {args.test_source} cases trainable"
            )
        else:
            test, ipp_train = ipp_train, []
            print("no configs/holdout.yaml: leave-one-out over all IPP cases (no AZ training)")
        print(f"terrain trained on {len(train)} {args.train_source} finds")

        def terrain_model(name, use, extra=()):
            m = HybridModel(
                [s for s in specs if s.name in use],
                builder,
                res=args.res,
                find_radius_m=args.radius,
                feature_res=args.feature_res,
                lam_w=args.lam_w,
                lam_region=args.lam_region,
            ).fit(train + list(extra))
            for f, mult in m.multipliers().items():
                print(f"  {name} {f}: {np.round(mult / mult[-1], 2)}")
            return m.frozen(name)

        names = {s.name for s in specs} - set(args.drop)
        if args.drop:
            print(f"Model B without: {', '.join(args.drop)}")
        primary = terrain_model("hybrid_ny", names)
        secondary = terrain_model("hybrid_ny_nostream", names - {"dist_stream_m"})
        with_az = terrain_model("hybrid_ny_az", names, extra=ipp_train) if ipp_train else None
        if with_az is not None:
            delta_az = np.round(with_az.delta.get("US-AZ", 0), 2)
            print(f"  hybrid_ny_az region correction US-AZ: {delta_az}")
        models = {
            "ring": RingModel,
            # Model A: the published model. Published features only, no cap, ring refitted.
            "model_a": lambda: BayesModel(
                specs, stack_provider=builder, feature_res=args.feature_res
            ),
            "hybrid_ny": primary.frozen,
            "hybrid_ny_nostream": secondary.frozen,
        }
        if with_az is not None:
            models["hybrid_ny_az"] = with_az.frozen

        def stacks(case, window):  # the fine stack HybridModel will ask for (cached)
            return builder(case, aggregate.fine_window(window, args.feature_res)[0])

        per_case = evaluate(
            models,
            test,
            split="loo",
            res=args.res,
            stack_provider=stacks,
            fixed_train=ipp_train if held else None,
        )
        pairs = [
            ("model_a", "ring"),
            ("hybrid_ny", "ring"),
            ("hybrid_ny_nostream", "ring"),
            ("hybrid_ny", "model_a"),
        ]
        if with_az is not None:
            pairs += [
                ("hybrid_ny_az", "ring"),
                ("hybrid_ny_az", "model_a"),
                ("hybrid_ny_az", "hybrid_ny"),
            ]
        rows = [
            paired(per_case, m, base, metric)
            for m, base in pairs
            for metric in ("mapscore", "log_p_find")
        ]
        result = pd.DataFrame(rows).round(3)
        args.out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        per_case.to_csv(args.out / f"gate_b_scores_{stamp}.csv", index=False)
        result.to_csv(args.out / f"gate_b_paired_{stamp}.csv", index=False)
        with pd.option_context("display.width", 140):
            print(summarize(per_case).to_string(index=False))
            print("\npaired per-case differences:")
            print(result.to_string(index=False))

        def verdict(model, base):
            g = result[
                (result["model"] == model)
                & (result["baseline"] == base)
                & (result["metric"] == "mapscore")
            ].iloc[0]
            v = "PASS" if g["ci95_low"] > 0 else "FAIL" if g["ci95_high"] < 0 else "INCONCLUSIVE"
            ci = f"CI {g['ci95_low']:+.3f} to {g['ci95_high']:+.3f}"
            return f"{model} vs {base}: {v} ({g['mean_diff']:+.3f}, {ci})"

        print("\nGate B, paired MapScore, 95% CI must exclude 0:")
        if with_az is not None:
            print("  roadmap gate  " + verdict("hybrid_ny_az", "model_a") + "  [B: NY + AZ train]")
            print("  AZ data helps " + verdict("hybrid_ny_az", "hybrid_ny"))
        print("  NY-only B     " + verdict("hybrid_ny", "model_a"))
        print("  vs ring       " + verdict("hybrid_ny", "ring"))
        print("  Model A       " + verdict("model_a", "ring"))
        print(f"written to {args.out}/")

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
