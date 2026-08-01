"""Command-line entry point for the dataset load and validation stage."""

import sys
from pathlib import Path

from router.dataset.contract import validate_row_count_parity
from router.dataset.loader import load_dataset_bundle
from router.dataset.timeline import build_user_timelines
from router.errors import DatasetError
from router.safety.gate import run_safety_gate

DEFAULT_DATASET_DIR = Path(__file__).resolve().parent.parent / "dataset"


def main(dataset_dir: Path = DEFAULT_DATASET_DIR) -> int:
    """Load, validate, and summarize the dataset; return a process exit code."""
    try:
        bundle = load_dataset_bundle(dataset_dir)
        timelines = build_user_timelines(bundle)
        validate_row_count_parity(bundle.messages, bundle.output_template)
    except DatasetError as exc:
        print(f"Dataset validation failed: {exc}", file=sys.stderr)
        return 1

    verdicts = run_safety_gate(bundle)
    blocked = sum(verdict.is_blocked for verdict in verdicts.values())
    borderline = sum(
        verdict.risk_type is not None and not verdict.is_blocked
        for verdict in verdicts.values()
    )
    clean = len(verdicts) - blocked - borderline

    print(
        f"Loaded {len(bundle.messages)} message(s) to route and built "
        f"interaction timelines for {len(timelines)} user(s)."
    )
    print(f"Safety gate: {blocked} blocked, {borderline} borderline, {clean} clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
