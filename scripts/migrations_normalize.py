#!/usr/bin/env python3
import re, sys, pathlib, argparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
MIG = ROOT / "supabase" / "migrations"

def wrap_enum_do_block(txt: str) -> str:
    # Guard any bare: CREATE TYPE public.<name> AS ENUM (...)
    # Skip if already inside a DO $$ ... $$ LANGUAGE plpgsql; directly above.
    def repl(m):
        name = m.group("name")
        body = m.group("body")
        # if already guarded nearby, keep as-is
        pre = txt[:m.start()]
        if re.search(r"DO\s*\$\$\s*BEGIN\s*$", pre.splitlines()[-1] if pre else "", re.I):
            return m.group(0)
        return (
f"DO $$\nBEGIN\n"
f"  IF NOT EXISTS (\n"
f"    SELECT 1 FROM pg_type t\n"
f"    JOIN pg_namespace n ON n.oid=t.typnamespace\n"
f"    WHERE t.typname='{name}' AND n.nspname='public'\n"
f"  ) THEN\n"
f"    CREATE TYPE public.{name} AS ENUM ({body});\n"
f"  END IF;\n"
f"END\n"
f"$$ LANGUAGE plpgsql;"
        )
    return re.sub(
        r"(?ims)^\s*CREATE\s+TYPE\s+public\.(?P<name>[a-z0-9_]+)\s+AS\s+ENUM\s*\((?P<body>[^;]+?)\)\s*;",
        repl,
        txt,
    )

def fix_pg_policy_filters(txt: str) -> str:
    txt = re.sub(r"\bpg_policies\b", "pg_policy", txt)
    txt = re.sub(r"\bpolicyname\b", "polname", txt)
    # schemaname='public' AND tablename='foo'  -> polrelid='public.foo'::regclass
    txt = re.sub(
        r"schemaname\s*=\s*'public'\s*AND\s*tablename\s*=\s*'([a-zA-Z0-9_]+)'",
        r"polrelid='public.\1'::regclass",
        txt,
    )
    txt = re.sub(
        r"tablename\s*=\s*'([a-zA-Z0-9_]+)'\s*AND\s*schemaname\s*=\s*'public'",
        r"polrelid='public.\1'::regclass",
        txt,
    )
    # dynamic: tablename = r.table_name  -> to_regclass(schema||'.'||table)
    txt = re.sub(
        r"tablename\s*=\s*r\.table_name",
        r"polrelid=to_regclass(quote_ident(r.table_schema)||'.'||quote_ident(r.table_name))",
        txt,
    )
    # drop lone schemaname filters (not in pg_policy)
    txt = re.sub(r"\s+AND\s+schemaname\s*=\s*'public'", "", txt)
    txt = re.sub(r"schemaname\s*=\s*r\.table_schema\s*AND\s*", "", txt)
    return txt

def fix_do_terminators(txt: str) -> str:
    # $ plpgsql; -> $$ LANGUAGE plpgsql;
    txt = re.sub(r"(?m)^\$\s*plpgsql;\s*$", "$$ LANGUAGE plpgsql;", txt)
    # END 12345 LANGUAGE plpgsql; -> END $$ LANGUAGE plpgsql;
    txt = re.sub(r"END\s+\d+\s+LANGUAGE\s+plpgsql\s*;", "END\n$$ LANGUAGE plpgsql;", txt, flags=re.I)
    # END LANGUAGE plpgsql; -> END $$ LANGUAGE plpgsql;
    txt = re.sub(r"END\s+LANGUAGE\s+plpgsql\s*;", "END\n$$ LANGUAGE plpgsql;", txt, flags=re.I)
    # DO 12345 -> DO $$
    txt = re.sub(r"(?m)^DO\s+\d+\s*$", "DO $$", txt, flags=re.I)
    # Ensure DO $$ BEGIN has newline after $$ for readability
    txt = re.sub(r"DO\s+\$\$\s*BEGIN", "DO $$\nBEGIN", txt, flags=re.I)
    return txt

def idempotent_misc(txt: str) -> str:
    # CREATE SCHEMA util_mig; -> CREATE SCHEMA IF NOT EXISTS util_mig;
    txt = re.sub(
        r"(?im)^\s*CREATE\s+SCHEMA\s+util_mig\s*;",
        "CREATE SCHEMA IF NOT EXISTS util_mig;",
        txt,
    )
    # remove psql meta-commands (e.g., \unrestrict)
    txt = re.sub(r"(?m)^\s*\\[A-Za-z].*$", "", txt)
    return txt

def normalize_text(txt: str) -> str:
    before = txt
    for fn in (fix_pg_policy_filters, fix_do_terminators, idempotent_misc, wrap_enum_do_block):
        txt = fn(txt)
    return txt

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="apply fixes in-place")
    args = ap.parse_args()

    changed = []
    for p in sorted(MIG.glob("*.sql")):
        if p.parent.name == "_archive":
            continue
        raw = p.read_text(encoding="utf-8")
        out = normalize_text(raw)
        if out != raw:
            changed.append(str(p.relative_to(ROOT)))
            if args.write:
                p.write_text(out, encoding="utf-8")
    if changed:
        print("\n".join(changed))
        sys.exit(1 if not args.write else 0)
    else:
        print("OK: no changes needed")

if __name__ == "__main__":
    main()
