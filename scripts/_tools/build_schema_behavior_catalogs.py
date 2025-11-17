#!/usr/bin/env python3
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = BASE_DIR.parent / "docs"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def read_tsv(path: Path):
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            rows.append(row)
    return rows


def build_triggers_md(rows):
    triggers = []
    for row in rows:
        if len(row) < 4:
            continue
        schema, table, trig_name, trig_def = row[:4]
        func_name = row[4] if len(row) > 4 else ""
        # Header rows have all of these non-empty; continuation lines from
        # pg_get_functiondef will have blanks here and only use column 0.
        if schema and table and trig_name and trig_def:
            triggers.append(
                {
                    "schema": schema,
                    "table": table,
                    "trigger_name": trig_name,
                    "trigger_def": trig_def,
                    "function_name": func_name,
                }
            )

    grouped = defaultdict(list)
    for t in triggers:
        grouped[(t["schema"], t["table"])].append(t)

    lines: list[str] = []
    lines.append("# Triggers catalog\n")
    lines.append(
        "Curated list of non-internal triggers discovered in the database, "
        "grouped by schema and table.\n"
    )

    for (schema, table) in sorted(grouped.keys()):
        lines.append(f"\n## `{schema}.{table}`\n")
        for t in sorted(grouped[(schema, table)], key=lambda x: x["trigger_name"]):
            lines.append(f"### `{t['trigger_name']}`\n")
            lines.append(f"- **Schema**: `{schema}`")
            lines.append(f"- **Table**: `{table}`")
            if t["function_name"]:
                lines.append(f"- **Function**: `{t['function_name']}`")
            lines.append("\n**Trigger definition**\n")
            lines.append("```sql")
            lines.append(t["trigger_def"])
            lines.append("```")
            lines.append("")

    return "\n".join(lines) + "\n"


def build_checks_md(rows):
    grouped = defaultdict(list)
    for row in rows:
        if len(row) < 4:
            continue
        schema, table, cname, expr = row[:4]
        if not schema or not table or not cname or not expr:
            continue
        grouped[(schema, table)].append({"name": cname, "expr": expr})

    lines: list[str] = []
    lines.append("# CHECK constraints catalog\n")
    lines.append(
        "This file lists all CHECK constraints discovered in the database, "
        "grouped by schema and table.\n"
    )

    for (schema, table) in sorted(grouped.keys()):
        lines.append(f"\n## `{schema}.{table}`\n")
        for c in sorted(grouped[(schema, table)], key=lambda x: x["name"]):
            lines.append(f"### `{c['name']}`\n")
            lines.append("**Expression**")
            lines.append("")
            lines.append("```sql")
            lines.append(c["expr"])
            lines.append("```")
            lines.append("")

    return "\n".join(lines) + "\n"


def build_defaults_md(rows):
    grouped = defaultdict(list)
    for row in rows:
        if len(row) < 4:
            continue
        schema, table, col, expr = row[:4]
        if not schema or not table or not col or expr is None:
            continue
        grouped[(schema, table)].append({"col": col, "expr": expr})

    lines: list[str] = []
    lines.append("# Column DEFAULTs catalog\n")
    lines.append(
        "This file lists all column defaults discovered in the database, "
        "grouped by schema and table.\n"
    )

    for (schema, table) in sorted(grouped.keys()):
        lines.append(f"\n## `{schema}.{table}`\n")
        for d in sorted(grouped[(schema, table)], key=lambda x: x["col"]):
            lines.append(f"- `{d['col']}`: `DEFAULT {d['expr']}`")
        lines.append("")

    return "\n".join(lines) + "\n"


def build_indexes_md(rows):
    grouped = defaultdict(list)
    for row in rows:
        if len(row) < 4:
            continue
        schema, table, iname, idef = row[:4]
        if not schema or not table or not iname or not idef:
            continue
        grouped[(schema, table)].append({"name": iname, "def": idef})

    lines: list[str] = []
    lines.append("# Non-primary indexes catalog\n")
    lines.append(
        "This file lists all non-primary indexes discovered in the database, "
        "grouped by schema and table.\n"
    )

    for (schema, table) in sorted(grouped.keys()):
        lines.append(f"\n## `{schema}.{table}`\n")
        for idx in sorted(grouped[(schema, table)], key=lambda x: x["name"]):
            lines.append(f"### `{idx['name']}`\n")
            lines.append("```sql")
            lines.append(idx["def"])
            lines.append("```")
            lines.append("")

    return "\n".join(lines) + "\n"


def main():
    triggers_rows = read_tsv(BASE_DIR / "schema_triggers.tsv")
    checks_rows = read_tsv(BASE_DIR / "schema_checks.tsv")
    defaults_rows = read_tsv(BASE_DIR / "schema_defaults.tsv")
    indexes_rows = read_tsv(BASE_DIR / "schema_indexes.tsv")

    (OUT_DIR / "schema_triggers.md").write_text(
        build_triggers_md(triggers_rows), encoding="utf-8"
    )
    (OUT_DIR / "schema_checks.md").write_text(
        build_checks_md(checks_rows), encoding="utf-8"
    )
    (OUT_DIR / "schema_defaults.md").write_text(
        build_defaults_md(defaults_rows), encoding="utf-8"
    )
    (OUT_DIR / "schema_indexes.md").write_text(
        build_indexes_md(indexes_rows), encoding="utf-8"
    )


if __name__ == "__main__":
    main()