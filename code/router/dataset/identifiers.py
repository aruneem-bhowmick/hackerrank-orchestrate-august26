"""Shared id-collection comparison primitives for parity/consistency guards.

Pure comparisons only — every caller keeps raising its own exception type
and message text; these functions never raise themselves.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import TypeVar

T = TypeVar("T")


def find_duplicates(values: Sequence[str]) -> list[str]:
    """Return the sorted set of values that appear more than once in values."""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        (duplicates if value in seen else seen).add(value)
    return sorted(duplicates)


def diff_id_sets(expected_ids: Iterable[str], actual_ids: Iterable[str]) -> tuple[list[str], list[str]]:
    """Return (missing, extra): ids in expected_ids not in actual_ids, and vice versa."""
    expected_set = set(expected_ids)
    actual_set = set(actual_ids)
    return sorted(expected_set - actual_set), sorted(actual_set - expected_set)


def find_mismatched_mapping_keys(mapping: Mapping[str, T], id_of: Callable[[T], str]) -> list[str]:
    """Return the sorted keys whose mapped value's own id (via id_of) does not match the key."""
    return sorted(key for key, value in mapping.items() if key != id_of(value))
