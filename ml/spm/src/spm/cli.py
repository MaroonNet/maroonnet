"""Command line entry point.

spm harmonize                 download source cases, validate, write data/cases/cases.csv
spm holdout --source mapscore --frac 0.33 --seed N      freeze a test set (configs/holdout.yaml)
"""

from __future__ import annotations

import argparse
from pathlib import Path

from spm.cases.harmonize import harmonize, load_cases
from spm.cases.split import DEFAULT_PATH as HOLDOUT_PATH
from spm.cases.split import make_holdout, write_holdout

ROOT = Path.cwd()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="spm")
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    sub = ap.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("harmonize", help="download + validate source cases")
    h.add_argument("--no-download", action="store_true")

    ho = sub.add_parser("holdout", help="draw and freeze the test set")
    ho.add_argument("--source", default="mapscore", help="cases of this source are split")
    ho.add_argument("--frac", type=float, default=1 / 3)
    ho.add_argument("--seed", type=int, required=True)
    ho.add_argument("--force", action="store_true", help="redraw an existing holdout")

    args = ap.parse_args(argv)

    if args.cmd == "harmonize":
        df, issues = harmonize(args.data, download=not args.no_download)
        print(f"kept {len(df)} cases -> {args.data / 'cases' / 'cases.csv'}")
        if len(issues):
            print(issues.groupby(["action", "reason"]).size().rename("n").to_string())
        print("\ncases per category:\n" + df["category"].value_counts().to_string())

    elif args.cmd == "holdout":
        pool = [c for c in load_cases(args.data) if c.source == args.source and c.ipp]
        ids = make_holdout(pool, args.frac, args.seed)
        path = write_holdout(
            ROOT / HOLDOUT_PATH, ids, args.source, args.frac, args.seed, args.force
        )
        print(f"{len(ids)} of {len(pool)} {args.source} cases frozen as the test set -> {path}")


if __name__ == "__main__":
    main()
