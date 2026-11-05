"""Command line entry point.

spm harmonize                 download source cases, validate, write data/cases/cases.csv
spm evaluate                  score models with leave-one-out, write results/
spm evaluate --models ring --res 5     reproduce MapScore's 5 m cells (slow, ~25M cells per case)
spm osm-lines PBF             extract trails/roads/streams from an OSM extract (run once per region)
spm nhd-lines GPKG            extract streams from a USGS NHD state GeoPackage (run once per region)
spm stacks --source nysdec    build and cache terrain stacks around each case
spm evaluate-terrain          leave-one-region-out terrain models on find-only cases (NYS DEC)
spm gate-b                    Model B (terrain from NY finds) vs the ring on Arizona
spm fit --model model_a       fit a model and write models/<name>.json
spm predict MODEL.json --ipp LON LAT --category hiker   probability raster + heatmap for one IPP
spm fetch-dem LON_MIN LAT_MIN LON_MAX LAT_MAX           pre-download 3DEP tiles for offline use
spm update PRED.tif --searched sectors.geojson          re-weight a raster after a search
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
from spm.geodata.grid import Window
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


def _apply_searched(pred, paths):
    """Multiply in the POD of each searched-area file (GeoJSON sectors or a POD GeoTIFF)."""
    from spm.io.coverage import pod_from_geojson, pod_from_raster
    from spm.models.update import apply_search, combine_pod

    layers = []
    for p in paths:
        is_tif = p.suffix.lower() in (".tif", ".tiff")
        layers.append(
            pod_from_raster(p, pred.window) if is_tif else pod_from_geojson(p, pred.window)
        )
    pod = combine_pod(layers)
    before = pred.p_outside
    pred = apply_search(pred, pod)
    print(
        f"searched {float((pod > 0).mean()):.1%} of cells; "
        f"outside this map {before:.1%} -> {pred.p_outside:.1%}"
    )
    return pred


def _write_prediction(pred, stem, case, stack, extra):
    from spm.io.raster import write_geotiff, write_heatmap_png, write_web_overlay

    ipp = (case.ipp.lon, case.ipp.lat) if case and case.ipp else None
    tif = write_geotiff(pred, stem.with_suffix(".tif"), ipp=ipp)
    png = write_heatmap_png(pred, stem.with_suffix(".png"), case=case, stack=stack)
    overlay = stem.with_name(stem.name + "_overlay")
    web = write_web_overlay(pred, overlay.with_suffix(".png"), overlay.with_suffix(".json"))
    flagged = 0.0 if pred.flags is None else float(pred.flags.mean())
    w = pred.window
    print(f"{pred.model} v{pred.model_version}: {w.n}x{w.n} at {w.res:g} m")
    print(f"outside this map: {pred.p_outside:.1%}; out-of-range cells: {flagged:.1%}")
    for p in (tif, png, web, web.with_suffix(".json"), *extra):
        print(f"  {p}")


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

    f = sub.add_parser("fit", help="fit a model and write it as JSON")
    f.add_argument("--model", default="model_a", choices=["model_a", "hybrid"])
    f.add_argument("--train-source", default="nysdec", help="find-only source for terrain weights")
    f.add_argument("--train-situation", default="Lost")
    f.add_argument("--ring-source", default="mapscore", help="IPP cases the ring is fitted on")
    f.add_argument("--res", type=float, default=100.0)
    f.add_argument("--feature-res", type=float, default=10.0)
    f.add_argument("--radius", type=float, default=1000.0)
    f.add_argument(
        "--drop", nargs="*", default=[], metavar="FEATURE", help="leave these features out of B"
    )
    f.add_argument("--lam-w", type=float, default=1.0, help="L2 pull of weights toward prior")
    f.add_argument(
        "--lam-region",
        type=float,
        default=300.0,
        help="L2 pull of region corrections toward 0 (300: 5-fold CV on the 71 AZ "
        "training cases, 2026-11-05; the Arizona cases help through the shared weights)",
    )
    f.add_argument("--lines", type=Path, nargs="*", default=None)
    f.add_argument("--streams", type=Path, nargs="*", default=None)
    f.add_argument("--out", type=Path, default=None, help="default: models/<model>.json")

    pr = sub.add_parser("predict", help="probability raster + heatmap for one IPP")
    pr.add_argument("model", type=Path, help="model JSON from `spm fit`")
    pr.add_argument("--ipp", type=float, nargs=2, metavar=("LON", "LAT"), required=True)
    pr.add_argument("--category", default="hiker")
    pr.add_argument("--region", default=None, help="region code for Model B's correction")
    pr.add_argument("--side", type=float, default=25_000.0, help="window side, metres")
    pr.add_argument(
        "--res",
        type=float,
        default=20.0,
        help="output cell size, metres (the model's weights are point multipliers, so any "
        "multiple of its feature resolution works; training used 100)",
    )
    pr.add_argument("--lines", type=Path, nargs="*", default=None)
    pr.add_argument("--streams", type=Path, nargs="*", default=None)
    pr.add_argument("--out", type=Path, default=None, help="output stem; default predictions/<ts>")
    pr.add_argument("--elapsed-h", type=float, default=None, help="hours since the IPP time")
    pr.add_argument("--max-slope-deg", type=float, default=None, help="impassable above this")
    pr.add_argument("--searched", type=Path, nargs="*", default=None, help="POD GeoJSON/GeoTIFF")

    up = sub.add_parser("update", help="re-weight a prediction raster after a search")
    up.add_argument("tif", type=Path, help="GeoTIFF from `spm predict` or an earlier update")
    up.add_argument("--searched", type=Path, nargs="+", required=True, help="POD GeoJSON/GeoTIFF")
    up.add_argument("--out", type=Path, default=None, help="output stem; default <tif stem>_u<N>")

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

    elif args.cmd == "fit":
        from spm.io.artifact import save_model
        from spm.models.hybrid import HybridModel

        builder = _builder(args, terrain)
        specs = load_specs(ROOT / "configs" / "prior_art.yaml")
        q = (yaml.safe_load((ROOT / "configs" / "ring_quantiles.yaml").read_text()) or {}).get(
            "categories"
        ) or {}
        q = {k: v for k, v in q.items() if v and all(v.get(x) for x in ("q25", "q50", "q75"))}
        cases, held = partition(load_cases(args.data), load_holdout(ROOT / HOLDOUT_PATH))
        if held:
            print(f"holdout: {len(held)} frozen test cases excluded from every fit")
        ring_cases = [c for c in cases if c.source == args.ring_source and c.ipp is not None]
        ring = RingModel(quantiles=q)
        if args.model == "model_a":
            model = BayesModel(
                specs, prior=ring, stack_provider=builder, feature_res=args.feature_res
            ).fit(ring_cases)
            train_n = 0
        else:
            train = [
                c
                for c in cases
                if c.source == args.train_source
                and c.ipp is None
                and args.train_situation in ("all", c.extra.get("situation"))
            ]
            model = HybridModel(
                [s for s in specs if s.name not in set(args.drop)],
                builder,
                prior=ring,
                res=args.res,
                find_radius_m=args.radius,
                feature_res=args.feature_res,
                lam_w=args.lam_w,
                lam_region=args.lam_region,
            )
            model.prior.fit(ring_cases)  # the ring comes from IPP cases, not find-only ones
            # find-only cases (no ring) plus the trainable IPP cases (ring strata, region delta)
            model.fit_strata(model.strata(train + ring_cases))
            train_n = model.n_train
            for name, mult in model.multipliers().items():
                print(f"  {name}: {np.round(mult / mult[-1], 2)}")
            print(f"  cap on stacked multipliers: {np.exp(model.max_logm):.1f}x")
        meta = {
            "terrain_train": {
                "source": args.train_source,
                "situation": args.train_situation,
                "n": train_n,
            },
            "ring_fit": {"source": args.ring_source, "n": len(ring_cases)},
            "holdout_excluded": len(held),
            "shrinkage": {"lam_w": args.lam_w, "lam_region": args.lam_region},
            "dropped_features": list(args.drop),
            "ring_published_categories": sorted(q),
            "ring_params": {
                k: {"mu": v[0], "sigma": v[1], "n": ring.n_fit.get(k)}
                for k, v in ring.params.items()
            },
            "line_files": [p.name for p in builder.line_files],
            "stream_files": [p.name for p in builder.stream_files],
        }
        out = args.out or ROOT / "models" / f"{args.model}.json"
        save_model(model, out, meta)
        print(f"ring categories: {', '.join(sorted(ring.params))}")
        print(f"wrote {out}")

    elif args.cmd == "predict":
        from spm.io.artifact import load_model
        from spm.schema import Case, LonLat

        builder = _builder(args, terrain)
        model = load_model(args.model, stack_provider=builder)
        lon, lat = args.ipp
        case = Case(
            case_id="live",
            source="cli",
            ipp=LonLat(lon, lat),
            category=args.category,
            region=args.region,
        )
        fr = model.feature_res
        if fr is not None and abs(args.res / fr - round(args.res / fr)) > 1e-9:
            raise SystemExit(f"--res {args.res:g} must be a multiple of the feature res {fr:g} m")
        window = Window.around(lon, lat, side_m=args.side, res=args.res)
        stack = builder(case, window)
        pred = model.predict(case, window, stack)
        pred.check()
        stem = args.out or ROOT / "predictions" / datetime.now().strftime("%Y%m%d-%H%M%S")
        extra = []
        if args.elapsed_h is not None:
            from spm.geodata.travel import travel_hours
            from spm.io.raster import write_band
            from spm.models.update import apply_time_cap

            hours = travel_hours(
                stack["dem"],
                window.res,
                window.rowcol(lon, lat),
                stack["trail_mask"] if stack.has("trail_mask") else None,
                args.max_slope_deg,
            )
            pred = apply_time_cap(pred, hours, args.elapsed_h)
            reach = float((hours <= args.elapsed_h).mean())
            print(f"travel-time cap at {args.elapsed_h:g} h: {reach:.0%} of cells reachable")
            extra.append(
                write_band(
                    stem.with_name(stem.name + "_travel_h.tif"),
                    window,
                    np.where(np.isfinite(hours), hours, -1.0),
                    "travel_hours_from_ipp",
                    speed="Tobler 1993 hiking function, x0.6 off trail",
                    unreachable=-1,
                )
            )
        if args.searched:
            pred = _apply_searched(pred, args.searched)
        pred.check()
        _write_prediction(pred, stem, case, stack, extra)

    elif args.cmd == "update":
        from spm.io.raster import read_geotiff
        from spm.schema import Case, LonLat

        pred, ipp = read_geotiff(args.tif)
        pred = _apply_searched(pred, args.searched)
        pred.check()
        n = pred.model.count("+search")
        stem = args.out or args.tif.with_name(f"{args.tif.stem.split('_u')[0]}_u{n}")
        case = Case(case_id="live", source="cli", ipp=LonLat(*ipp), category="?") if ipp else None
        _write_prediction(pred, stem, case, None, [])

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
