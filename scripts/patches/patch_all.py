#!/usr/bin/env python3
from __future__ import annotations
import re, sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # …/carp_v2
changed = []

def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")

def write_if_changed(p: Path, s: str):
    old = read(p)
    if old != s:
        p.write_text(s, encoding="utf-8")
        changed.append(str(p.relative_to(ROOT)))

def ensure(pattern: str, repl: str, s: str, flags=re.DOTALL):
    if re.search(pattern, s, flags):
        return s
    return s + ("\n" if not s.endswith("\n") else "") + repl + "\n"

def sub(pattern: str, repl: str, s: str, flags=re.DOTALL):
    return re.sub(pattern, repl, s, flags=flags)

# ---- 1) queries.py : robust load_fish_overview -----------------------------
def patch_queries_py():
    p = ROOT / "supabase" / "queries.py"
    if not p.exists(): return
    s = read(p)
    # Ensure imports at top
    s = re.sub(
        r"(?s)\A.*?from sqlalchemy import text",
        "from __future__ import annotations\n\nfrom typing import Any, Dict, List, Optional\nimport pandas as pd\nfrom sqlalchemy import text",
        s, count=1)
    # Replace load_fish_overview function
    s = re.sub(
        r"def\s+load_fish_overview\(.*?\n\s*return\s+pd\.read_sql_query\(.*?\)\n",
        (
        "def load_fish_overview(engine, q: Optional[str] = None, limit: int = 1000) -> pd.DataFrame:\n"
        "    try:\n"
        "        lim = max(1, min(int(limit), 10000))\n"
        "    except Exception:\n"
        "        lim = 1000\n\n"
        "    params: Dict[str, Any] = {\"lim\": lim}\n"
        "    filters: List[str] = []\n"
        "    if q and q.strip():\n"
        "        params[\"p\"] = f\"%{q.strip()}%\"\n"
        "        filters.append(\n"
        "            \"(\"\n"
        "            \"  v.fish_code ilike %(p)s\"\n"
        "            \"  or coalesce(v.name,'') ilike %(p)s\"\n"
        "            \"  or coalesce(v.transgene_base_code_filled,'') ilike %(p)s\"\n"
        "            \"  or coalesce(v.allele_code_filled,'') ilike %(p)s\"\n"
        "            \"  or coalesce(v.created_by_enriched,'') ilike %(p)s\"\n"
        "            \"  or coalesce(v.batch_label,'') ilike %(p)s\"\n"
        "            \")\"\n"
        "        )\n"
        "    where_sql = (\" where \" + \" and \".join(filters)) if filters else \"\"\n\n"
        "    sql = f\"\"\"\n"
        "    select\n"
        "      f.id as id,\n"
        "      v.fish_code,\n"
        "      v.name,\n"
        "      v.transgene_base_code_filled  as transgene_base_code,\n"
        "      v.allele_code_filled          as allele_code,\n"
        "      v.allele_name_filled          as allele_name,\n"
        "      v.line_building_stage,\n"
        "      v.date_birth,\n"
        "      v.age_days,\n"
        "      v.age_weeks,\n"
        "      v.batch_label,\n"
        "      v.last_plasmid_injection_at,\n"
        "      v.plasmid_injections_text,\n"
        "      v.last_rna_injection_at,\n"
        "      v.rna_injections_text,\n"
        "      v.created_at,\n"
        "      v.created_by_enriched         as created_by\n"
        "    from public.v_fish_overview_with_label v\n"
        "    left join public.fish f on f.fish_code = v.fish_code\n"
        "    {where_sql}\n"
        "    order by v.fish_code\n"
        "    limit %(lim)s\n"
        "    \"\"\"\n"
        "    return pd.read_sql_query(sql, con=engine, params=params)\n"
        ),
        s, flags=re.DOTALL)
    write_if_changed(p, s)

# ---- 2) alloc_link.py : single ensure_transgene_pair -----------------------
def patch_alloc_link():
    p = ROOT / "supabase" / "ui" / "lib" / "alloc_link.py"
    if not p.exists(): return
    s = read(p)
    if "from sqlalchemy import text" not in s:
        s = s.replace("from typing import Optional", "from typing import Optional\nfrom sqlalchemy import text")
    # Remove earlier duplicate def ensure_transgene_pair (keep the last one)
    defs = list(re.finditer(r"\ndef\s+ensure_transgene_pair\([^\)]*\):", s))
    if len(defs) > 1:
        first = defs[0].start()
        # remove the first definition block
        s = re.sub(r"\ndef\s+ensure_transgene_pair\([^\)]*\):(.*?)\n(?=#|\n\w|def\s|\Z)", "\n", s, count=1, flags=re.DOTALL)
    # Ensure correct body (base -> allele)
    s = re.sub(
        r"def\s+ensure_transgene_pair\([^\)]*\):(.*?)\n(?=#|\n\w|def\s|\Z)",
        (
            "def ensure_transgene_pair(conn, base: str, allele_number: int):\n"
            "    \"\"\"Ensure parent transgene base exists, then the allele (idempotent).\"\"\"\n"
            "    conn.execute(\n"
            "        text(\"\"\"\n"
            "            insert into public.transgenes (transgene_base_code)\n"
            "            values (:b)\n"
            "            on conflict (transgene_base_code) do nothing\n"
            "        \"\"\"), {\"b\": base},\n"
            "    )\n"
            "    conn.execute(\n"
            "        text(\"\"\"\n"
            "            insert into public.transgene_alleles (transgene_base_code, allele_number)\n"
            "            values (:b, :a)\n"
            "            on conflict (transgene_base_code, allele_number) do nothing\n"
            "        \"\"\"), {\"b\": base, \"a\": int(allele_number)},\n"
            "    )\n"
        ),
        s, flags=re.DOTALL)
    write_if_changed(p, s)

# ---- 3) new_fish_from_cross.py : remove fish_code in INSERT ----------------
def patch_cross_page():
    # filename has emoji; glob by prefix
    candidates = list((ROOT / "supabase" / "ui" / "pages").glob("03_*_new_fish_from_cross.py"))
    if not candidates: return
    p = candidates[0]
    s = read(p)
    s2 = re.sub(r"\(id,\s*fish_code,\s*name,\s*created_by,\s*date_birth\)", "(id, name, created_by, date_birth)", s)
    write_if_changed(p, s2)

# ---- 4) 02_new_fish_from_csv.py : codes capture + recent filtered ----------
def patch_csv_page():
    candidates = list((ROOT / "supabase" / "ui" / "pages").glob("02_*_new_fish_from_csv.py"))
    if not candidates: return
    p = candidates[0]
    s = read(p)
    # Ensure new_codes list declaration
    s = re.sub(
        r"created_rows:\s*List\[Dict\[str,\s*Any\]\]\s*=\s*\[\]\n(#.*?\n)?for _\, r in to_insert\.iterrows\(\):",
        "created_rows: List[Dict[str, Any]] = []\nnew_codes: list[str] = []\n\\g<1>for _, r in to_insert.iterrows():",
        s, flags=re.DOTALL)
    # Append to new_codes after created_rows.append(dict(row))
    s = s.replace(
        "created_rows.append(dict(row))",
        "created_rows.append(dict(row))\nnew_codes.append(row[\"fish_code\"])"
    )
    # Print caption with codes after created_ct
    s = s.replace(
        "created_ct = len(created_rows)",
        "created_ct = len(created_rows)\nst.caption(f\"new fish_code(s): {', '.join(new_codes)}\")"
    )
    # Ensure load_log_fish uses df_norm.loc[r.name, \"__row_key__\"]
    s = re.sub(
        r"rk\)\n\s*\}\),\s*\{\s*\"fid\":\s*row\[\"id\"\],\s*\"seed\":\s*seed_batch_id,\s*\"rk\":\s*r\.get\(\"__row_key__\"\)\s*\}\),",
        "rk)\n    }), {\"fid\": row[\"id\"], \"seed\": seed_batch_id, \"rk\": df_norm.loc[r.name, \"__row_key__\"]}),",
        s)
    # Ensure to_insert base cols don't include row_key/meta
    s = re.sub(
        r"base_cols\s*=\s*\[.*?__seed_batch_id__.*?\]",
        "base_cols = [\"name\",\"created_by\",\"date_birth\"]",
        s, flags=re.DOTALL)
    # Filter recent rows by batch_label = seed_batch_id
    s = re.sub(
        r"select \*\s*from public\.v_fish_overview_with_label\s*limit 50",
        "select *\n        from public.v_fish_overview_with_label\n        where batch_label = %(seed)s\n        limit 50",
        s)
    # Ensure try/except wraps recent block (already there in your latest)
    if "try:" not in s or "except Exception as e:" not in s:
        # minimal: wrap simple try/except
        s = s.replace(
            "st.markdown(\"#### Recent rows (from `v_fish_overview_with_label`)\")",
            "st.markdown(\"#### Recent rows (from `v_fish_overview_with_label`)\")\ntry:"
        )
        s += "\nexcept Exception as e:\n    st.warning(f\"Could not read v_fish_overview_with_label yet: {e}\")\n"
    write_if_changed(p, s)

def main():
    patch_queries_py()
    patch_alloc_link()
    patch_cross_page()
    patch_csv_page()

    if not changed:
        print("✅ No changes needed (all patches already applied).")
    else:
        print("✅ Patched files:")
        for c in changed:
            print(" -", c)
        print("\nTip: run your app with:\n  APP_FORCE_LOCAL=1 scripts/carp_local_start\n")

if __name__ == "__main__":
    main()