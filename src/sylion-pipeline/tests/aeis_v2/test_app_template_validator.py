from sylion.aeis_v2.apps_v2 import validate_app_template_dict


def _valid():
    return {
        "id": "x", "name_pl": "n", "description_pl": "d",
        "object_type_ids": ["a", "b", "c"],
        "widget_ids": ["w1", "w2", "w3"],
        "tags": ["t1", "t2", "t3", "t4", "t5"],
    }


def test_validate_accepts_valid_dict():
    ok, errors = validate_app_template_dict(_valid())
    assert ok is True and errors == []


def test_validate_rejects_missing_string_field():
    d = _valid(); d.pop("id")
    ok, errors = validate_app_template_dict(d)
    assert ok is False and "id must be str" in errors


def test_validate_rejects_wrong_list_type():
    d = _valid(); d["object_type_ids"] = "abc"
    ok, errors = validate_app_template_dict(d)
    assert ok is False and "object_type_ids must be list[str]" in errors


def test_validate_rejects_non_string_list_items():
    d = _valid(); d["widget_ids"] = ["w1", 2, "w3"]
    ok, errors = validate_app_template_dict(d)
    assert ok is False and "widget_ids must be list[str]" in errors


def test_validate_rejects_out_of_range_lengths():
    d = _valid(); d["tags"] = ["t1", "t2", "t3", "t4"]
    ok, errors = validate_app_template_dict(d)
    assert ok is False and "tags len must be 5-8" in errors
