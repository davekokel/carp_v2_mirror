import sys, pathlib, re

def usage():
    print("usage: guard_migration.py --kind plasmids|rnas --file path.sql", file=sys.stderr)
    sys.exit(2)

args = sys.argv[1:]
if len(args) != 3 or args[0] != "--kind" or args[2] == "":
    usage()
kind = args[1]
file = pathlib.Path(args[2])
sql = file.read_text()

# Skip if already guarded (very simple heuristic)
if re.search(r'\bDO\s+\$\$|\bDO\s+\$[A-Za-z0-9_]+\$', sql):
    print(f"skip (already guarded): {file}")
    sys.exit(0)

if kind == "plasmids":
    guard_if = "to_regclass('public.plasmids') IS NOT NULL"
elif kind == "rnas":
    # guard if either rnas or injected_rna_treatments is present (module deployed)
    guard_if = "(to_regclass('public.rnas') IS NOT NULL OR to_regclass('public.injected_rna_treatments') IS NOT NULL)"
else:
    print("unknown kind", file=sys.stderr); sys.exit(2)

wrapped = f"""DO $$\nBEGIN\n  IF {guard_if} THEN\n{sql.rstrip()}\n  END IF;\nEND\n$$;\n"""
# backup and write
bak = file.with_suffix(file.suffix + ".orig")
if not bak.exists():
    bak.write_text(sql)
file.write_text(wrapped)
print(f"guarded: {file}")
