from sylion.aeis_v2.lifecycle_v2 import LIFECYCLE_PG_VIEW_DDL


def test_lifecycle_pg_view_ddl_contains_materialized_view() -> None:
    assert "CREATE MATERIALIZED VIEW IF NOT EXISTS current_idea_state" in (
        LIFECYCLE_PG_VIEW_DDL
    )


def test_lifecycle_pg_view_ddl_contains_idea_id_index() -> None:
    assert "CREATE INDEX IF NOT EXISTS current_idea_state_idea_id_idx" in (
        LIFECYCLE_PG_VIEW_DDL
    )
