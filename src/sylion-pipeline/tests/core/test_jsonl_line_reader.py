import json

import pytest

from sylion.core.jsonl_line_reader import JsonlLineReader


def test_empty_file(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text("", encoding="utf-8")
    assert list(JsonlLineReader(path)) == []


def test_valid_lines(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text('{"id":1}\n{"id":2}\n', encoding="utf-8")
    assert list(JsonlLineReader(path)) == [{"id": 1}, {"id": 2}]


def test_mixed_valid_invalid_with_skip(tmp_path, caplog):
    path = tmp_path / "audit.jsonl"
    path.write_text('{"id":1}\nnope\n{"id":2}\n', encoding="utf-8")
    assert list(JsonlLineReader(path)) == [{"id": 1}, {"id": 2}]
    assert "Skipping invalid JSONL line 2" in caplog.text


def test_mixed_valid_invalid_without_skip_raises(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text(f'{json.dumps({"id": 1})}\nnope\n', encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        list(JsonlLineReader(path, skip_invalid=False))
