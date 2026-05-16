"""Concurrency & determinism tests for AEIS Advisor — Variants.

Equal load 100× equal — results must be deterministic.
"""

from __future__ import annotations

import concurrent.futures
import threading

from sylion.aeis.advisor.variants.generator import generate_variants
from sylion.aeis.advisor.variants.service import get_variants_service


class TestVariantsDeterminism:
    """Determinism under repeated identical load."""

    def _strip_nondeterministic(self, variant_set):
        """Return comparable dicts excluding UUIDs and timestamps."""
        result = []
        for v in variant_set.variants:
            d = v.to_dict()
            d.pop("variant_id", None)
            d.pop("generated_at", None)
            result.append(d)
        return result

    def test_100x_equal_load_deterministic(self):
        """100 identical calls must produce identical variant shapes."""
        ctx = {"context_id": "det_test", "project_type": "software"}
        baseline = generate_variants(ctx)
        baseline_stripped = self._strip_nondeterministic(baseline)

        for i in range(99):
            vs = generate_variants(ctx)
            stripped = self._strip_nondeterministic(vs)
            assert stripped == baseline_stripped, f"Mismatch at iteration {i}"

    def test_service_100x_equal_load_deterministic(self):
        """Service-level 100 identical calls must be deterministic."""
        svc = get_variants_service()
        ctx = {"context_id": "svc_det", "project_type": "software"}
        baseline = svc.generate_variants(ctx)
        baseline_stripped = self._strip_nondeterministic(baseline)

        for i in range(99):
            vs = svc.generate_variants(ctx)
            stripped = self._strip_nondeterministic(vs)
            assert stripped == baseline_stripped, f"Service mismatch at iteration {i}"

    def test_thread_pool_concurrency_no_races(self):
        """Concurrent generation from threads must not crash or corrupt."""
        ctx = {"context_id": "thr_test", "project_type": "software"}
        results = []
        lock = threading.Lock()

        def worker():
            vs = generate_variants(ctx)
            with lock:
                results.append(len(vs.variants))

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(worker) for _ in range(50)]
            for f in futures:
                f.result()

        assert all(r == 3 for r in results), "Some thread got wrong variant count"

    def test_service_concurrent_calls_isolated(self):
        """Concurrent service calls must return isolated histories."""
        svc = get_variants_service()
        contexts = [{"context_id": f"concurrent_{i}"} for i in range(20)]

        def worker(ctx):
            return svc.generate_variants(ctx)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = {pool.submit(worker, ctx): ctx for ctx in contexts}
            for fut in concurrent.futures.as_completed(futures):
                vs = fut.result()
                assert len(vs.variants) == 3
                # Ensure history keyed by context_id, not overwritten
                assert vs.context_id == futures[fut]["context_id"]

    def test_cost_ordering_stable_across_runs(self):
        """Cost ordering (cost_saving ≤ balanced ≤ aggressive) must hold every time."""
        for _ in range(50):
            vs = generate_variants()
            costs = {v.name: v.estimated_cost_usd for v in vs.variants}
            assert costs["cost_saving"] <= costs["balanced"]
            assert costs["balanced"] <= costs["aggressive"]
