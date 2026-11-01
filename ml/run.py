"""Run the frozen v1 protocol in an isolated local directory; preserve reports."""

import argparse
import re
import runpy
import sys

from guardian_ml import paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", help="Local reproduction ID; letters, digits, underscore, hyphen")
    parser.add_argument(
        "command", choices=["dataset", "train", "evaluate", "report", "predictor", "test"]
    )
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,47}", args.run_id):
        parser.error("Invalid run ID")
    directory = paths.ROOT / "ml/runs" / args.run_id
    paths.DATA = directory / "data"
    paths.ARTIFACTS = directory / "artifacts"
    paths.REPORTS = directory / "reports"
    paths.ensure_directories()
    if args.command == "test":
        import pytest

        raise SystemExit(pytest.main([str(paths.ROOT / "ml/tests"), "-q", *args.arguments]))
    sys.argv = ["guardian_ml." + args.command, *args.arguments]
    runpy.run_module("guardian_ml." + args.command, run_name="__main__")


if __name__ == "__main__":
    main()
