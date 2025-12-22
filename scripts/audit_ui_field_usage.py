from __future__ import annotations

import ast
import os
import re
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

from sqlalchemy import create_engine, text


PAGES_DIR = Path("carp_app/ui/pages")


REL_NAME_RE = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b")


def _read_text(fp: Path) -> str:
    return fp.read_text(encoding="utf-8")


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _engine():
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("[STOP] DB_URL is not set (use_local first).")
    return create_engine(url)


def _public_relation_names(cx) -> Tuple[Set[str], Set[str]]:
    rows = cx.execute(
        text(
            """
            select table_name, table_type
            from information_schema.tables
            where table_schema='public'
              and table_type in ('BASE TABLE','VIEW')
            """
        )
    ).fetchall()
    tables = {r[0] for r in rows if r[1] == "BASE TABLE"}
    views = {r[0] for r in rows if r[1] == "VIEW"}
    return tables, views


def _public_relation_columns(cx) -> Dict[str, Set[str]]:
    rows = cx.execute(
        text(
            """
            select table_name, column_name
            from information_schema.columns
            where table_schema='public'
            order by table_name, ordinal_position
            """
        )
    ).fetchall()
    m: Dict[str, Set[str]] = {}
    for t, c in rows:
        m.setdefault(t, set()).add(c)
    return m


def _string_literals(tree: ast.AST) -> Set[str]:
    out: Set[str] = set()

    class V(ast.NodeVisitor):
        def visit_Constant(self, node: ast.Constant):
            if isinstance(node.value, str):
                out.add(node.value)
            self.generic_visit(node)

        def visit_Str(self, node: ast.Str):  # py<3.8
            out.add(node.s)
            self.generic_visit(node)

    V().visit(tree)
    return out


def _extract_sql_strings(tree: ast.AST) -> List[str]:
    out: List[str] = []

    def add(s: str):
        s2 = (s or "").strip()
        if not s2:
            return
        if "select" in s2.lower() or "from" in s2.lower() or "join" in s2.lower():
            out.append(s2)

    class V(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call):
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    add(a.value)
                elif isinstance(a, ast.JoinedStr):
                    parts = []
                    for v in a.values:
                        if isinstance(v, ast.Constant) and isinstance(v.value, str):
                            parts.append(v.value)
                    if parts:
                        add("".join(parts))
            self.generic_visit(node)

    V().visit(tree)
    return out


def _relations_in_sql(sql: str, known: Set[str]) -> Set[str]:
    s = _norm_ws(sql)
    rels: Set[str] = set()

    for m in re.finditer(r"\bfrom\s+public\.([a-zA-Z_][a-zA-Z0-9_]*)\b", s, flags=re.IGNORECASE):
        nm = m.group(1)
        if nm in known:
            rels.add(nm)

    for m in re.finditer(r"\bjoin\s+public\.([a-zA-Z_][a-zA-Z0-9_]*)\b", s, flags=re.IGNORECASE):
        nm = m.group(1)
        if nm in known:
            rels.add(nm)

    for m in re.finditer(r"\bfrom\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", s, flags=re.IGNORECASE):
        nm = m.group(1)
        if nm in known:
            rels.add(nm)

    for m in re.finditer(r"\bjoin\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", s, flags=re.IGNORECASE):
        nm = m.group(1)
        if nm in known:
            rels.add(nm)

    return rels


def _select_list(sql: str) -> str:
    s = sql
    m = re.search(r"(?is)\bselect\b(.*?)\bfrom\b", s)
    if not m:
        return ""
    return m.group(1) or ""


def _tokens_from_select(sel: str) -> Set[str]:
    s = _norm_ws(sel)
    if not s:
        return set()

    toks = set()
    for t in REL_NAME_RE.findall(s):
        toks.add(t)
    return toks


def main() -> None:
    eng = _engine()
    with eng.begin() as cx:
        tables, views = _public_relation_names(cx)
        rel_cols = _public_relation_columns(cx)

    known = set(tables) | set(views)
    view_names = set(views)

    rows_rel: List[Dict[str, str]] = []
    rows_sql: List[Dict[str, str]] = []
    by_rel_fields: Dict[str, Set[str]] = {}

    pages = sorted(PAGES_DIR.glob("*.py"))
    if not pages:
        raise SystemExit(f"[STOP] no pages found at {PAGES_DIR}")

    for fp in pages:
        src = _read_text(fp)
        try:
            tree = ast.parse(src)
        except Exception as e:
            rows_rel.append({"page": str(fp), "relation": "", "field": "", "kind": "PARSE_ERROR", "note": str(e)})
            continue

        lits = _string_literals(tree)

        # relation mentions from raw text: public.<rel> OR bare rel names
        rels_hit: Set[str] = set()
        for m in re.finditer(r"\bpublic\.([a-zA-Z_][a-zA-Z0-9_]*)\b", src):
            nm = m.group(1)
            if nm in known:
                rels_hit.add(nm)
        for nm in known:
            if nm in rels_hit:
                continue
            if re.search(rf"\b{re.escape(nm)}\b", src):
                rels_hit.add(nm)

        if not rels_hit:
            rows_rel.append({"page": str(fp), "relation": "", "field": "", "kind": "NO_RELATION_FOUND", "note": ""})
        else:
            for rel in sorted(rels_hit):
                cols = rel_cols.get(rel, set())
                used_fields = sorted(lits & cols)
                if not used_fields:
                    rows_rel.append({"page": str(fp), "relation": rel, "field": "", "kind": "REL_FOUND_NO_FIELDS", "note": ""})
                    continue
                by_rel_fields.setdefault(rel, set()).update(used_fields)
                for f in used_fields:
                    rows_rel.append({"page": str(fp), "relation": rel, "field": f, "kind": "string_literal∩rel_cols", "note": ""})

        sqls = _extract_sql_strings(tree)
        for i, raw in enumerate(sqls, start=1):
            rels2 = _relations_in_sql(raw, known)
            if not rels2:
                continue

            sel = _select_list(raw)
            toks = _tokens_from_select(sel)
            if not toks:
                continue

            for r in sorted(rels2):
                if r not in view_names:
                    continue
                cols = rel_cols.get(r, set())
                for t in sorted(toks):
                    if t in cols:
                        rows_sql.append({"page": str(fp), "sql_index": str(i), "relation": r, "field": t, "kind": "SQL_SELECT_COL", "note": ""})
                        by_rel_fields.setdefault(r, set()).add(t)

    out_rel = Path("/tmp/carp_relation_field_usage_current.csv")
    out_sql = Path("/tmp/carp_sql_field_usage_current.csv")

    with out_rel.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["page", "relation", "field", "kind", "note"])
        w.writeheader()
        w.writerows(rows_rel)

    with out_sql.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["page", "sql_index", "relation", "field", "kind", "note"])
        w.writeheader()
        w.writerows(rows_sql)

    used_views = sorted([v for v in by_rel_fields.keys() if v in view_names and len(by_rel_fields[v]) > 0])

    print("WROTE", out_rel)
    print("WROTE", out_sql)
    print("PAGES_SCANNED", len(pages))
    print("USED_VIEWS_WITH_FIELDS", len(used_views))
    for v in used_views:
        print(v)


if __name__ == "__main__":
    main()
