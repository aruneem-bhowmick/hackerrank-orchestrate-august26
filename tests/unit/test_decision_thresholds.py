"""Unit tests for router.decision.thresholds.bound01."""

import pytest

from router.decision.thresholds import bound01


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.5, 0.5),
        (0.0, 0.0),
        (1.0, 1.0),
        (-0.3, 0.0),
        (1.3, 1.0),
        (-1000.0, 0.0),
        (1000.0, 1.0),
    ],
)
def test_bound01_clamps_to_the_unit_interval(value: float, expected: float):
    """bound01 clamps any real value into [0, 1], inclusive at both ends."""
    assert bound01(value) == expected
