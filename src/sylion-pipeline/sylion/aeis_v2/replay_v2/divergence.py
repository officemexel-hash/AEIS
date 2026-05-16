from __future__ import annotations

import math


def cosine_similarity_floats(a: list[float], b: list[float]) -> float:
    if not a or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return 0.0 if na == 0.0 or nb == 0.0 else dot / (na * nb)


def levenshtein_distance(a: list, b: list) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        curr = [i]
        for j, y in enumerate(b, 1):
            curr.append(min(prev[j] + 1, curr[-1] + 1, prev[j - 1] + (x != y)))
        prev = curr
    return prev[-1]


def jaccard_set_similarity(a: list, b: list) -> float:
    sa, sb = set(a), set(b)
    return 1.0 if not sa and not sb else len(sa & sb) / max(1, len(sa | sb))


def compute_weighted_divergence(
    orig_decisions: list,
    replay_decisions: list,
    orig_final: list[float],
    replay_final: list[float],
) -> float:
    max_len = max(len(orig_decisions), len(replay_decisions))
    seq = 0.0 if max_len == 0 else levenshtein_distance(
        orig_decisions, replay_decisions
    ) / max_len
    score = 0.6 * (1.0 - cosine_similarity_floats(orig_final, replay_final))
    score += 0.4 * seq
    return max(0.0, min(1.0, score))


def compute_divergence_score(
    orig_decisions: list,
    replay_decisions: list,
    orig_final: list[float],
    replay_final: list[float],
) -> float:
    return compute_weighted_divergence(
        orig_decisions, replay_decisions, orig_final, replay_final
    )


__all__ = [
    "compute_divergence_score",
    "compute_weighted_divergence",
    "cosine_similarity_floats",
    "jaccard_set_similarity",
    "levenshtein_distance",
]
