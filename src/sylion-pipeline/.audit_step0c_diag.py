"""Diagnostic: confirm what status code 'other' represents."""
import os
os.environ["SYLION_RBAC_DISABLED"] = "1"
os.environ["SYLION_RATE_LIMIT_DISABLED"] = "1"

from collections import Counter
from fastapi.testclient import TestClient
from sylion.api.app import app

client = TestClient(app)
spec = app.openapi()

statuses = Counter()
samples_by_code: dict[int, list[tuple[str, str]]] = {}

count = 0
for path, ops in spec["paths"].items():
    if "get" not in ops:
        continue
    if "{" in path:
        continue  # skip path-param routes for this diag
    if not path.startswith("/api/v1/"):
        continue
    count += 1
    if count > 200:
        break
    try:
        resp = client.get(path)
    except Exception as exc:
        statuses[-1] += 1
        samples_by_code.setdefault(-1, []).append((path, f"{type(exc).__name__}: {exc}"))
        continue
    sc = resp.status_code
    statuses[sc] += 1
    if sc not in (200, 404, 422):
        samples_by_code.setdefault(sc, []).append((path, resp.text[:200]))

print(f"hit {count} routes")
print()
print("status distribution:")
for sc, n in sorted(statuses.items()):
    print(f"  {sc}: {n}")
print()
for sc, samples in sorted(samples_by_code.items()):
    if sc in (200, 404, 422):
        continue
    print(f"--- status {sc} samples ---")
    for path, body in samples[:3]:
        print(f"  {path}")
        print(f"    {body[:180]}")
