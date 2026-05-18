# PROD R3 MemoryPlane Canonical Write PASS1/PASS2

Date: 2026-05-18
Roadmap items: `C.1 Global memory plane`, `Luka 2 Memory Split`
Decision pack: `results/decisions/PROD-D3-MEMORY-PLANE-CANONICAL-WRITE_evidence_pack.json`
Status: `FROZEN_2X` for canonical MemoryPlane write, project-scoped search and evidence/provenance enforcement

## Scope

This freeze covers:

- New `sylion.memory.plane.MemoryPlane` as the canonical durable write service for new memory entries.
- `MemoryEntry` fields: `entry_id`, `content`, `project_id`, `evidence_id`, `provenance`, `metadata`, `content_hash`, `created_by`, `created_at`.
- Writes require non-empty `content` and `provenance.source`.
- Writes auto-register an Evidence Spine JSON artifact when `evidence_id` is not supplied.
- Writes index content into the memory indexer with `project_id`.
- Search returns only MemoryPlane entries and supports `project_id` filtering.
- Public hooks: `sylion.memory.write`, `sylion.memory.search`, `get_memory_plane`.
- Bootstrap initializes MemoryPlane on the same shared memory SQLite database and indexer.
- API endpoints:
  - `POST /api/v1/memory/plane/write`
  - `GET /api/v1/memory/plane/search`
  - `GET /api/v1/memory/plane/projects/{project_id}`
  - `GET /api/v1/memory/plane/entries/{entry_id}`
  - `GET /api/v1/memory/plane/stats`
- `/api/v1/memory/stats` now includes the canonical plane stats.

## Files Changed

- `src/sylion-pipeline/sylion/memory/plane.py`
- `src/sylion-pipeline/sylion/memory/bootstrap.py`
- `src/sylion-pipeline/sylion/memory/__init__.py`
- `src/sylion-pipeline/sylion/api/memory_routes.py`
- `src/sylion-pipeline/tests/memory/test_memory_plane.py`
- `src/sylion-pipeline/tests/memory/test_bootstrap.py`

## Verification PASS1

```text
python -m pytest src\sylion-pipeline\tests\memory src\sylion-pipeline\tests\test_memory.py src\sylion-pipeline\tests\test_memory_retrieval_project_filter.py src\sylion-pipeline\tests\test_memory_retrieval.py src\sylion-pipeline\tests\test_memory_indexer.py src\sylion-pipeline\tests\test_memory_evidence_store.py src\sylion-pipeline\tests\test_memory_bootstrap_unified.py src\sylion-pipeline\tests\test_api_integration.py -q
275 passed, 2 xfailed, 6 xpassed, 7 warnings
```

## Verification PASS2

```text
python -m pytest src\sylion-pipeline\tests\memory src\sylion-pipeline\tests\test_memory.py src\sylion-pipeline\tests\test_memory_retrieval_project_filter.py src\sylion-pipeline\tests\test_memory_retrieval.py src\sylion-pipeline\tests\test_memory_indexer.py src\sylion-pipeline\tests\test_memory_evidence_store.py src\sylion-pipeline\tests\test_memory_bootstrap_unified.py src\sylion-pipeline\tests\test_api_integration.py -q
275 passed, 2 xfailed, 6 xpassed, 7 warnings

python -m compileall -q src\sylion-pipeline\sylion\memory\plane.py src\sylion-pipeline\sylion\api\memory_routes.py src\sylion-pipeline\sylion\memory\bootstrap.py
PASS

git diff --check
PASS
```

Known warnings are historical deprecation warnings plus one existing `PytestReturnNotNoneWarning` in `test_api_integration.py`.

## Boundary

This freeze establishes and verifies the canonical write path. It does not yet migrate every legacy writer in kanon, evidence_store, self_model_store, Obsidian sync, project runtime DB or advisor memory to call `MemoryPlane.write()`. Those legacy surfaces remain read/compatibility modules until follow-up integration work moves their writes behind the plane.

## Rollback

Rollback strategy is recorded in:

```text
results/decisions/PROD-D3-MEMORY-PLANE-CANONICAL-WRITE_evidence_pack.json
```

Expected rollback time: 20 minutes.
Data loss risk: `NONE` for code rollback; existing `memory_entries` rows can remain inert.
