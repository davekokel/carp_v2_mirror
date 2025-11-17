import re
from pathlib import Path

p = Path("supabase/migrations")
for file in sorted(p.glob("*.sql")):
    if file.name.endswith(".bak"):
        continue

    new_name = None

    # Pattern: 2025-10-01_wide_links.sql → 20251001_000000_wide_links.sql
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})_(.+)\.sql$", file.name)
    if m:
        y, mo, d, desc = m.groups()
        new_name = f"{y}{mo}{d}_000000_{desc}.sql"

    # Pattern: 20250922201746_2025-09-22_add_xyz.sql → 20250922_000000_add_xyz.sql
    elif m := re.match(r"^(\d{14})_(\d{4}-\d{2}-\d{2})_(.+)\.sql$", file.name):
        ts, _, desc = m.groups()
        new_name = f"{ts[:8]}_000000_{desc}.sql"

    # Pattern: 20250930_legacy_map_and_next_allele.sql or 20250930_100500_guarded_grants.sql
    elif m := re.match(r"^(\d{8})(?:_(\d{6}))?_(.+)\.sql$", file.name):
        date_part, time_part, desc = m.groups()
        time_part = time_part or "000000"
        new_name = f"{date_part}_{time_part}_{desc}.sql"

    # Pattern: 20250922160000_genetics_core.sql → 20250922_160000_genetics_core.sql
    elif m := re.match(r"^(\d{8})(\d{6})_(.+)\.sql$", file.name):
        date_part, time_part, desc = m.groups()
        new_name = f"{date_part}_{time_part}_{desc}.sql"

    if new_name and new_name != file.name:
        new_path = file.parent / new_name
        print(f"Renaming: {file.name} → {new_path.name}")
        file.rename(new_path)
    elif not new_name:
        print(f"❌ No match: {file.name}")