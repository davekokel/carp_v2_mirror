#!/usr/bin/env python3
import re, sys, pathlib, argparse, hashlib

DO_BLOCK_RE = re.compile(
    r"""(?P<prefix>\s*)DO\s*(?P<dol>\$\$|\$[A-Za-z0-9_]*\$)?(?P<body>.*?)(?P=dol)\s*;?""",
    re.DOTALL | re.IGNORECASE,
)
LANG_INLINE_RE = re.compile(r"\bLANGUAGE\s+plpgsql\b", re.IGNORECASE)
CREATE_ENUM_RE = re.compile(
    r"^\s*CREATE\s+TYPE\s+(?P<name>[A-Za-z_][A-Za-z0-9_\.]*)\s+AS\s+ENUM\s*\((?P<vals>[^;]*?)\)\s*;?",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)

def normalize_do_blocks(sql: str) -> str:
    def fix(m):
        prefix = m.group("prefix") or ""
        dol = m.group("dol") or "$$"
        body = (m.group("body") or "").strip()
        body = LANG_INLINE_RE.sub("", body).strip()
        has_begin = re.search(r"^\s*BEGIN\b", body, re.IGNORECASE)
        has_end = re.search(r"\bEND\s*;?\s*$", body, re.IGNORECASE)
        if not has_begin or not has_end:
            body = f"BEGIN\n{body.rstrip(';')};\nEND;"
        return f"{prefix}DO {dol}\n{body}\n{dol} LANGUAGE plpgsql;"
    return DO_BLOCK_RE.sub(fix, sql)

def _split_enum_vals(vals_raw: str):
    out, cur, q, esc = [], [], False, False
    for ch in vals_raw:
        if esc:
            cur.append(ch); esc = False; continue
        if ch == "\\":
            cur.append(ch); esc = True; continue
        if ch == "'":
            q = not q; cur.append(ch); continue
        if ch == "," and not q:
            s = "".join(cur).strip()
            if s: out.append(s)
            cur = []; continue
        cur.append(ch)
    s = "".join(cur).strip()
    if s: out.append(s)
    return out

def _sig(vals_list):
    return hashlib.sha1(("|".join(vals_list)).encode("utf-8")).hexdigest()

def dedupe_enums(sql: str) -> str:
    seen = {}
    def repl(m):
        full = m.group(0)
        name = m.group("name")
        vals = [v.strip() for v in _split_enum_vals(m.group("vals").strip())]
        key = name.lower()
        if key not in seen:
            seen[key] = {"sig": _sig(vals), "vals": vals}
            return f"CREATE TYPE {name} AS ENUM ({', '.join(vals)});"
        if seen[key]["sig"] == _sig(vals):
            return (
                "DO $$\nBEGIN\n"
                f"  IF NOT EXISTS (\n"
                f"    SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace\n"
                f"    WHERE t.typname='{name.split('.')[-1].lower()}' AND t.typtype='e'\n"
                f"  ) THEN\n"
                f"    CREATE TYPE {name} AS ENUM ({', '.join(vals)});\n"
                f"  END IF;\n"
                "END;\n$$ LANGUAGE plpgsql;"
            )
        first = seen[key]["vals"]
        missing = [v for v in vals if v not in first]
        if not missing:
            return (
                "DO $$\nBEGIN\n"
                f"  IF NOT EXISTS (\n"
                f"    SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace\n"
                f"    WHERE t.typname='{name.split('.')[-1].lower()}' AND t.typtype='e'\n"
                f"  ) THEN\n"
                f"    CREATE TYPE {name} AS ENUM ({', '.join(vals)});\n"
                f"  END IF;\n"
                "END;\n$$ LANGUAGE plpgsql;"
            )
        return "\n".join([f"ALTER TYPE {name} ADD VALUE IF NOT EXISTS {v};" for v in missing])
    return CREATE_ENUM_RE.sub(repl, sql)

def normalize_file(p: pathlib.Path) -> str:
    txt = p.read_text(encoding="utf-8")
    txt = normalize_do_blocks(txt)
    txt = dedupe_enums(txt)
    return txt

def normalize_tree(root: pathlib.Path):
    changed = []
    for f in sorted(root.glob("*.sql")):
        before = f.read_text(encoding="utf-8")
        after = normalize_file(f)
        if before != after:
            f.write_text(after, encoding="utf-8")
            changed.append(f)
    return changed

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("migration_dir", nargs="?", default="supabase/migrations")
    args = ap.parse_args()
    root = pathlib.Path(args.migration_dir)
    if not root.exists():
        print(f"missing dir: {root}", file=sys.stderr); sys.exit(2)
    changed = normalize_tree(root)
    print(f"normalized: {len(changed)} file(s)")
    for p in changed: print(f" - {p}")

if __name__ == "__main__":
    main()
