import hashlib

from sylion.core.embedding_hash_collision_detector import EmbeddingHashCollisionDetector


def test_check_returns_no_collisions_for_distinct_hashes():
    assert EmbeddingHashCollisionDetector().check(["a", "b", "c"]) == []


def test_check_returns_single_collision(monkeypatch):
    values = iter(["same000000000000", "same000000000000", "diff000000000000"])
    monkeypatch.setattr(hashlib, "sha256", lambda _: type("H", (), {"hexdigest": lambda self: next(values)})())
    collisions = EmbeddingHashCollisionDetector().check(["a", "b", "c"])
    assert [(c.hash, c.texts) for c in collisions] == [("same000000000000", ["a", "b"])]


def test_check_returns_three_collisions(monkeypatch):
    values = iter(["h1" * 8, "h1" * 8, "h2" * 8, "h2" * 8, "h3" * 8, "h3" * 8])
    monkeypatch.setattr(hashlib, "sha256", lambda _: type("H", (), {"hexdigest": lambda self: next(values)})())
    collisions = EmbeddingHashCollisionDetector().check(["a", "b", "c", "d", "e", "f"])
    assert [(c.hash, c.texts) for c in collisions] == [("h1" * 8, ["a", "b"]), ("h2" * 8, ["c", "d"]), ("h3" * 8, ["e", "f"])]
