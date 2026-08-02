"""Run the complete batch router and write a validated submission CSV."""

import argparse
import sys
from pathlib import Path

from router.dataset.contract import validate_row_count_parity
from router.dataset.loader import DatasetBundle, load_dataset_bundle
from router.dataset.timeline import build_user_timelines
from router.decision.pipeline import run_decision_fusion
from router.errors import DatasetError
from router.ingestion.pipeline import run_media_ingestion
from router.output.calibration import (
    CalibrationReport,
    build_sample_bundle,
    format_calibration_report,
    measure_calibration,
)
from router.output.validation import validate_output_frame
from router.output.writer import build_output_frame, write_output_csv
from router.personalization.pipeline import run_personalization
from router.safety.gate import run_safety_gate

DEFAULT_DATASET_DIR = Path(__file__).resolve().parent.parent / "dataset"


def main(dataset_dir: Path = DEFAULT_DATASET_DIR, output_path: Path | None = None) -> int:
    """Run routing, calibration, validation, and CSV writing; return an exit code.

    The production artifact is written only after all routing stages, sample
    calibration, and output validation complete. Project validation failures
    and filesystem errors are reported to stderr and return a nonzero status.
    """
    output_path = output_path or dataset_dir / "output.csv"
    try:
        bundle = load_dataset_bundle(dataset_dir)
        validate_row_count_parity(bundle.messages, bundle.output_template)
        decisions, normalized, verdicts, evidence, timelines = _route_bundle(bundle, dataset_dir)
        calibration = _calibrate(bundle, dataset_dir)
        output = build_output_frame(bundle.messages["message_id"].tolist(), decisions)
        validate_output_frame(bundle.messages, output)
        written_path = write_output_csv(output, output_path)
    except (DatasetError, OSError) as exc:
        print(f"Submission failed: {exc}", file=sys.stderr)
        return 1

    _print_summary(bundle, timelines, normalized, verdicts, evidence, decisions, calibration, written_path)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse optional dataset and output path overrides for the batch command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=DEFAULT_DATASET_DIR,
        help="directory containing the required dataset CSV files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="destination CSV path (defaults to <dataset-dir>/output.csv)",
    )
    return parser.parse_args(argv)


def _route_bundle(bundle: DatasetBundle, dataset_dir: Path):
    """Run the complete upstream routing pipeline for one loaded bundle."""
    timelines = build_user_timelines(bundle)
    normalized = run_media_ingestion(bundle, dataset_dir)
    verdicts = run_safety_gate(bundle, normalized)
    evidence = run_personalization(normalized, bundle, timelines)
    decisions = run_decision_fusion(bundle, normalized, verdicts, evidence)
    return decisions, normalized, verdicts, evidence, timelines


def _calibrate(bundle: DatasetBundle, dataset_dir: Path) -> CalibrationReport:
    """Route solved sample inputs through the production path and measure agreement."""
    sample_bundle = build_sample_bundle(bundle)
    sample_decisions, _, _, _, _ = _route_bundle(sample_bundle, dataset_dir)
    return measure_calibration(sample_decisions, bundle.sample_messages)


def _print_summary(
    bundle: DatasetBundle,
    timelines: dict[str, list[dict]],
    normalized: dict,
    verdicts: dict,
    evidence: dict,
    decisions: dict,
    calibration: CalibrationReport,
    output_path: Path,
) -> None:
    """Print concise batch, safety, media, evidence, decision, and output summaries."""
    blocked = sum(verdict.is_blocked for verdict in verdicts.values())
    borderline = sum(
        verdict.risk_type is not None and not verdict.is_blocked
        for verdict in verdicts.values()
    )
    clean = len(verdicts) - blocked - borderline
    media_messages = [msg for msg in normalized.values() if msg.media_type in ("image", "voice")]
    media_failures = sum(msg.media_failure for msg in media_messages)
    evidence_found = sum(bool(item.evidence_ids) for item in evidence.values())
    mention_overrides = sum(bool(item.personalization_signals["mention_override"]) for item in evidence.values())
    notify_count = sum(record.action == "notify" for record in decisions.values())
    digest_count = sum(record.action == "digest" for record in decisions.values())
    mute_count = sum(record.action == "mute" for record in decisions.values())

    print(
        f"Loaded {len(bundle.messages)} message(s) to route and built "
        f"interaction timelines for {len(timelines)} user(s)."
    )
    print(f"Safety gate: {blocked} blocked, {borderline} borderline, {clean} clean.")
    print(
        f"Media ingestion: {len(media_messages)} image/voice message(s) processed, "
        f"{media_failures} failed to produce usable text."
    )
    print(
        f"Personalization: {evidence_found} message(s) have relevant evidence; "
        f"{mention_overrides} muted-group mention override(s) detected."
    )
    print(f"Decision fusion: {notify_count} notify, {digest_count} digest, {mute_count} mute.")
    print(format_calibration_report(calibration))
    print(f"Wrote validated submission: {output_path} ({len(decisions)} row(s)).")


if __name__ == "__main__":
    arguments = parse_args()
    sys.exit(main(arguments.dataset_dir, arguments.output))
