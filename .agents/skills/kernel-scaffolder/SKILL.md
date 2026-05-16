---
name: kernel-scaffolder
description: Scaffolds a new SYLION kernel module with manifest, proto stub, migration, golden tests
---

# Kernel Scaffolder

## When to use
- Creating a new module in any class (A-O)
- Starting a new plan (P01-P20)
- After contract freeze approval

## Inputs
- module_id: string (e.g. "core.module_registry")
- class: string (A-O)
- port: int
- owner_plan: string (P01-P20)
- depends_on: list of module_ids

## Outputs
- manifest.yaml, __init__.py, main module .py, proto stub, 001_init.sql, golden tests (3 min)

## Execution steps
1. Read Ksiega for module class definition
2. Read Masterplan for plan assignment
3. Create directory structure
4. Generate manifest.yaml
5. Create __init__.py
6. Create main module (SQLite-backed, thread-safe, EventBus pattern)
7. Create proto stub
8. Create migration SQL
9. Create 3+ golden tests

## Safety rules
- Never modify existing modules without D3+
- All new modules start DRAFT
- Dependencies must exist

## Properties
- parallel-safe: true
- idempotent: true
