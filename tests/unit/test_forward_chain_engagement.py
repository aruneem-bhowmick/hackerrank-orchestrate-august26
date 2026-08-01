"""Unit tests for the aggregate forward-chain open-rate statistic."""

import pandas as pd

from router.safety.gate import compute_forward_chain_open_rate

_HISTORY_COLUMNS = ["message_id", "user_id", "forwarded_count"]
_EVENT_COLUMNS = ["message_id", "user_id", "message_opened"]


def _history(rows: list[tuple[str, str, str]]) -> pd.DataFrame:
    """Build a minimal message_history frame from (message_id, user_id, forwarded_count) rows."""
    return pd.DataFrame(rows, columns=_HISTORY_COLUMNS)


def _events(rows: list[tuple[str, str, str]]) -> pd.DataFrame:
    """Build a minimal message_events frame from (message_id, user_id, message_opened) rows."""
    return pd.DataFrame(rows, columns=_EVENT_COLUMNS)


def test_computes_mean_open_rate_among_high_forward_messages_only():
    """Only forwarded_count >= threshold rows contribute to the rate."""
    history = _history(
        [
            ("h1", "u_1", "10"),  # high forward, opened
            ("h2", "u_1", "9"),  # high forward, not opened
            ("h3", "u_1", "0"),  # low forward, excluded regardless of open state
        ]
    )
    events = _events(
        [
            ("h1", "u_1", "1"),
            ("h2", "u_1", "0"),
            ("h3", "u_1", "1"),
        ]
    )
    rate = compute_forward_chain_open_rate(history, events)
    assert rate == 0.5


def test_returns_none_when_no_rows_meet_the_forward_count_filter():
    """An undefined rate (no qualifying rows) is None, not 0.0."""
    history = _history([("h1", "u_1", "0"), ("h2", "u_1", "1")])
    events = _events([("h1", "u_1", "1"), ("h2", "u_1", "0")])
    assert compute_forward_chain_open_rate(history, events) is None


def test_all_high_forward_messages_opened_gives_rate_one():
    """All qualifying rows opened yields a rate of exactly 1.0."""
    history = _history([("h1", "u_1", "8"), ("h2", "u_1", "9")])
    events = _events([("h1", "u_1", "1"), ("h2", "u_1", "1")])
    assert compute_forward_chain_open_rate(history, events) == 1.0


def test_no_high_forward_messages_opened_gives_rate_zero():
    """No qualifying rows opened yields a rate of exactly 0.0, distinguishable from None."""
    history = _history([("h1", "u_1", "8"), ("h2", "u_1", "9")])
    events = _events([("h1", "u_1", "0"), ("h2", "u_1", "0")])
    assert compute_forward_chain_open_rate(history, events) == 0.0


def test_rows_without_a_matching_event_are_excluded_from_the_rate():
    """A history row with no event match contributes no known outcome."""
    history = _history([("h1", "u_1", "8"), ("h2", "u_1", "9")])
    events = _events([("h1", "u_1", "1")])  # h2 has no matching event row
    assert compute_forward_chain_open_rate(history, events) == 1.0
