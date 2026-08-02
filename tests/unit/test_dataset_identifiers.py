"""Unit coverage for the shared id-collection comparison primitives."""

from router.dataset.identifiers import diff_id_sets, find_duplicates, find_mismatched_mapping_keys


def test_find_duplicates_returns_empty_for_no_repeats():
    """A sequence with every value unique reports no duplicates."""
    assert find_duplicates(["one", "two", "three"]) == []


def test_find_duplicates_returns_sorted_repeated_values():
    """Values appearing more than once are reported once each, sorted."""
    assert find_duplicates(["b", "a", "b", "c", "a", "a"]) == ["a", "b"]


def test_find_duplicates_handles_empty_input():
    """An empty sequence has no duplicates."""
    assert find_duplicates([]) == []


def test_diff_id_sets_reports_no_difference_for_equal_sets():
    """Identical id collections produce empty missing and extra lists."""
    assert diff_id_sets(["one", "two"], ["two", "one"]) == ([], [])


def test_diff_id_sets_reports_missing_only():
    """An expected id absent from actual is reported as missing."""
    assert diff_id_sets(["one", "two"], ["one"]) == (["two"], [])


def test_diff_id_sets_reports_extra_only():
    """An actual id absent from expected is reported as extra."""
    assert diff_id_sets(["one"], ["one", "two"]) == ([], ["two"])


def test_diff_id_sets_reports_both_missing_and_extra():
    """Disjoint collections report both sides independently, each sorted."""
    assert diff_id_sets(["one", "three"], ["two", "one"]) == (["three"], ["two"])


def test_find_mismatched_mapping_keys_returns_empty_when_all_keys_match():
    """A mapping whose keys equal every value's own id has no mismatches."""
    mapping = {"one": ("one", "a"), "two": ("two", "b")}

    assert find_mismatched_mapping_keys(mapping, id_of=lambda value: value[0]) == []


def test_find_mismatched_mapping_keys_returns_sorted_mismatched_keys():
    """Keys whose value disagrees on its own id are reported, sorted."""
    mapping = {"one": ("different", "a"), "two": ("two", "b"), "three": ("also-different", "c")}

    assert find_mismatched_mapping_keys(mapping, id_of=lambda value: value[0]) == ["one", "three"]
