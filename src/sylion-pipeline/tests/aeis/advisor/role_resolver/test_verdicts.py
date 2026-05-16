from sylion.aeis.advisor.role_resolver.verdicts import compute_distribution


def test_compute_distribution_counts_approve():
    rows = [{"model_id": "a", "verdict": "approve"}, {"model_id": "b", "verdict": "approve"}]
    assert compute_distribution(rows) == {"approve": 2, "reject": 0, "conditional": 0}


def test_compute_distribution_counts_mixed_verdicts():
    rows = [{"model_id": "a", "verdict": "approve"}, {"model_id": "b", "verdict": "reject"}, {"model_id": "c", "verdict": "conditional"}]
    assert compute_distribution(rows) == {"approve": 1, "reject": 1, "conditional": 1}


def test_compute_distribution_ignores_unknown_verdicts():
    rows = [{"model_id": "a", "verdict": "defer"}, {"model_id": "b", "verdict": "reject"}]
    assert compute_distribution(rows) == {"approve": 0, "reject": 1, "conditional": 0}
