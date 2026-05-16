from sylion.core import deduplicate_by_key


def test_deduplicate_by_key_returns_empty_list_for_empty_input():
    assert deduplicate_by_key([], "id") == []


def test_deduplicate_by_key_keeps_all_items_when_values_are_unique():
    items = [
        {"id": "a", "name": "Alpha"},
        {"id": "b", "name": "Beta"},
        {"id": "c", "name": "Gamma"},
    ]

    assert deduplicate_by_key(items, "id") == items


def test_deduplicate_by_key_keeps_first_occurrence_for_duplicate_values():
    first = {"id": "a", "name": "Alpha"}
    duplicate = {"id": "a", "name": "Alpha newer"}
    other = {"id": "b", "name": "Beta"}

    assert deduplicate_by_key([first, duplicate, other], "id") == [first, other]


def test_deduplicate_by_key_preserves_input_order_of_first_seen_items():
    first_b = {"id": "b", "name": "Beta"}
    first_a = {"id": "a", "name": "Alpha"}
    second_b = {"id": "b", "name": "Beta duplicate"}
    first_c = {"id": "c", "name": "Gamma"}
    second_a = {"id": "a", "name": "Alpha duplicate"}

    assert deduplicate_by_key(
        [first_b, first_a, second_b, first_c, second_a],
        "id",
    ) == [first_b, first_a, first_c]
