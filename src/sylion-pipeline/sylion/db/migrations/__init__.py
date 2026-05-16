"""SYLION DB migrations — sequenced schema upgrades.

Each migration exposes ``up(conn)`` and ``down(conn)`` callables. Migrations
are intentionally idempotent (CREATE IF NOT EXISTS / DROP IF EXISTS) so they
can be replayed safely against partially-migrated databases.
"""
