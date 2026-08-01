from pathlib import Path

import pytest

from router.dataset.loader import load_dataset_bundle
from router.dataset.timeline import build_user_timelines
from router.errors import TimelineJoinError

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def _load(fixture_name: str):
    fixture_dir = FIXTURES_DIR / fixture_name
    return load_dataset_bundle(fixture_dir, repo_root=fixture_dir)


def test_build_user_timelines_on_valid_fixture_has_exact_pinned_order():
    timelines = build_user_timelines(_load("dataset_valid"))
    assert set(timelines) == {"u_001", "u_002"}
    assert [entry["message_id"] for entry in timelines["u_001"]] == [
        "hist_0001",
        "hist_0002",
    ]
    assert [entry["message_id"] for entry in timelines["u_002"]] == ["hist_0003"]


def test_build_user_timelines_raises_on_orphan_event_fixture():
    with pytest.raises(TimelineJoinError, match="hist_9999"):
        build_user_timelines(_load("dataset_timeline_orphan_event"))


def test_build_user_timelines_raises_on_user_mismatch_fixture():
    with pytest.raises(TimelineJoinError, match="hist_0001"):
        build_user_timelines(_load("dataset_timeline_user_mismatch"))
