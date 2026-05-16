from __future__ import annotations

import re


class PgSchemaDiff:
    _TABLE_RE = re.compile(
        r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+([^\s(]+)\s*\((.*?)\);",
        re.IGNORECASE | re.DOTALL,
    )
    _SKIP = {"constraint", "primary", "foreign", "unique", "check", "exclude"}

    @classmethod
    def _tables(cls, sql: str) -> dict[str, list[str]]:
        tables = {}
        for name, body in cls._TABLE_RE.findall(sql):
            cols = []
            for part in re.split(r",\s*(?![^()]*\))", body):
                line = part.strip()
                if not line:
                    continue
                head = line.split(None, 1)[0].strip('"').lower()
                if head not in cls._SKIP:
                    cols.append(head)
            tables[name.lower()] = cols
        return tables

    @classmethod
    def diff(cls, schema_a_sql: str, schema_b_sql: str) -> list[str]:
        a, b = cls._tables(schema_a_sql), cls._tables(schema_b_sql)
        out = [f"missing table: {t}" for t in sorted(a.keys() - b.keys())]
        out += [f"extra table: {t}" for t in sorted(b.keys() - a.keys())]
        for t in sorted(a.keys() & b.keys()):
            if a[t] != b[t]:
                miss = sorted(set(a[t]) - set(b[t]))
                extra = sorted(set(b[t]) - set(a[t]))
                out.append(f"changed table: {t} missing={miss} extra={extra}")
        return out
