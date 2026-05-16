import json
from concurrent.futures import ThreadPoolExecutor

from sylion.core.audit_jsonl_writer import AuditJsonlWriter


def test_append_single(tmp_path):
    path = tmp_path / "audit.jsonl"
    AuditJsonlWriter(path).append({"id": 1, "text": "zażółć"})
    assert [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()] == [{"id": 1, "text": "zażółć"}]


def test_append_multi(tmp_path):
    path = tmp_path / "audit.jsonl"
    writer = AuditJsonlWriter(path)
    writer.append({"id": 1})
    writer.append({"id": 2})
    assert [json.loads(x)["id"] for x in path.read_text(encoding="utf-8").splitlines()] == [1, 2]


def test_missing_parent_dir_auto_created(tmp_path):
    path = tmp_path / "nested" / "audit.jsonl"
    AuditJsonlWriter(path).append({"ok": True})
    assert path.exists() and json.loads(path.read_text(encoding="utf-8")) == {"ok": True}


def test_lock_free_under_concurrent_appends(tmp_path):
    path = tmp_path / "audit.jsonl"
    writer = AuditJsonlWriter(path)
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(lambda i: writer.append({"id": i}), range(40)))
    rows = [json.loads(x)["id"] for x in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 40 and set(rows) == set(range(40))
