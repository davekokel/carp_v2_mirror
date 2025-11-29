from __future__ import annotations

import pandas as pd
from pathlib import Path
from rapidfuzz import fuzz, process

BASE = Path("seed_kits")

parents_xlsx = BASE / "legacy_wrangling_v2/raw/Unique_parent_names__mom_dad_combined__preview_dqm.xlsx"
lines_xlsx   = BASE / "2025-11-15-121231-autoload/fish.xlsx"
out_csv      = BASE / "legacy_wrangling_v2/working/fish_aliases_v11.csv"

# --- load parent labels ---
df_par = pd.read_excel(parents_xlsx)
parent_labels = sorted({str(x).strip() for x in df_par.iloc[:,0].dropna() if str(x).strip()})

# --- load line nicknames ---
df_lines = pd.read_excel(lines_xlsx)
line_nicks = sorted({str(x).strip() for x in df_lines["nickname"].dropna()})

rows = []

for pl in parent_labels:
    matches = process.extract(
        pl,
        line_nicks,
        scorer=fuzz.token_sort_ratio,
        limit=1,
    )

    if matches:
        best_nick, score = matches[0][0], matches[0][1]
        if score >= 55:
            rows.append({"alias": pl, "line_nickname": best_nick, "score": score})
        else:
            rows.append({"alias": pl, "line_nickname": "", "score": score})
    else:
        rows.append({"alias": pl, "line_nickname": "", "score": 0})

df_out = pd.DataFrame(rows)
df_out.to_csv(out_csv, index=False)
print(f"[OK] wrote {len(df_out)} alias rows → {out_csv}")
print("[INFO] Non-empty mappings:", df_out[df_out['line_nickname'] != ""].shape[0])
