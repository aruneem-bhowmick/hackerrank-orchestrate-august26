"""Integration tests for the timeline join against real loaded fixtures."""

import pytest

from router.dataset.timeline import build_user_timelines
from router.errors import TimelineJoinError


def test_build_user_timelines_on_valid_fixture_has_exact_pinned_order(load_fixture_bundle):
    """The join output for a known-good fixture matches an exact, pinned order."""
    timelines = build_user_timelines(load_fixture_bundle("dataset_valid"))
    assert set(timelines) == {"u_001", "u_002"}
    assert [entry["message_id"] for entry in timelines["u_001"]] == [
        "hist_0001",
        "hist_0002",
    ]
    assert [entry["message_id"] for entry in timelines["u_002"]] == ["hist_0003"]


def test_build_user_timelines_raises_on_orphan_event_fixture(load_fixture_bundle):
    """A fixture with an orphaned event row fails the join, naming the message_id."""
    with pytest.raises(TimelineJoinError, match="hist_9999"):
        build_user_timelines(load_fixture_bundle("dataset_timeline_orphan_event"))


def test_build_user_timelines_raises_on_user_mismatch_fixture(load_fixture_bundle):
    """A fixture with a cross-file user_id disagreement fails the join."""
    with pytest.raises(TimelineJoinError, match="hist_0001"):
        build_user_timelines(load_fixture_bundle("dataset_timeline_user_mismatch"))
