from sylion.aeis_v2.db import PgSchemaDiff


def test_pg_schema_diff_identical() -> None:
    sql = "CREATE TABLE public.users (id bigint, email text);"
    assert PgSchemaDiff.diff(sql, sql) == []


def test_pg_schema_diff_missing_column() -> None:
    a = "CREATE TABLE public.users (id bigint, email text);"
    b = "CREATE TABLE public.users (id bigint);"
    assert PgSchemaDiff.diff(a, b) == [
        "changed table: public.users missing=['email'] extra=[]"
    ]


def test_pg_schema_diff_missing_table() -> None:
    a = "CREATE TABLE public.users (id bigint); CREATE TABLE public.logs (id bigint);"
    b = "CREATE TABLE public.users (id bigint);"
    assert PgSchemaDiff.diff(a, b) == ["missing table: public.logs"]
