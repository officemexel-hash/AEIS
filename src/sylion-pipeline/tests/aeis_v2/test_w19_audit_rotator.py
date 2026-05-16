from datetime import datetime, timedelta
from sylion.aeis_v2.policy_v2.audit_rotator import W19AuditRotator


def test_no_rotate_when_under_limit(tmp_path):
    p = tmp_path / "audit.jsonl"; p.write_text("x")
    assert W19AuditRotator.rotate_if_size_exceeds(p, max_mb=1) is None and p.exists()


def test_rotate_uses_next_sequence(tmp_path):
    p = tmp_path / "audit.jsonl"; p.write_bytes(b"x" * 2)
    d = datetime.now().strftime("%Y-%m-%d")
    (tmp_path / f"audit.jsonl.{d}.1.jsonl").write_text("")
    out = W19AuditRotator.rotate_if_size_exceeds(p, max_mb=0.000001)
    assert out.name == f"audit.jsonl.{d}.2.jsonl" and out.exists() and not p.exists()


def test_collect_old_deletes_older_rotations(tmp_path):
    p = tmp_path / "audit.jsonl"; today = datetime.now().date()
    old = tmp_path / f"audit.jsonl.{(today - timedelta(days=31)):%Y-%m-%d}.1.jsonl"; old.write_text("")
    keep = tmp_path / f"audit.jsonl.{(today - timedelta(days=5)):%Y-%m-%d}.1.jsonl"; keep.write_text("")
    dead = W19AuditRotator.collect_old(p, keep_days=30)
    assert dead == [old] and not old.exists() and keep.exists()


def test_collect_old_ignores_invalid_names(tmp_path):
    p = tmp_path / "audit.jsonl"; junk = tmp_path / "audit.jsonl.bad.1.jsonl"; junk.write_text("")
    W19AuditRotator.collect_old(p, keep_days=0)
    assert junk.exists()
