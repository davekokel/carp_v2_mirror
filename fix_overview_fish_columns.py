from pathlib import Path
import re

root = Path("carp_app/ui/pages")
for f in root.glob("*overview_fish.py"):
    text = f.read_text()
    new = re.sub(
        r"COALESCE\(v\.genotype_pretty,''\)\s*ILIKE\s*:q",
        "COALESCE(v.transgene_pretty,'') ILIKE :q OR COALESCE(v.genotype_rollup,'') ILIKE :q",
        text,
        flags=re.S,
    )
    if new != text:
        f.write_text(new)
        print("✅ patched", f)
