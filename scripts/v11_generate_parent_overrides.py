from pathlib import Path
import pandas as pd
import re

BASE = Path("seed_kits")
parents_xlsx = BASE / "legacy_wrangling_v2/raw/Unique_parent_names__mom_dad_combined__preview_dqm.xlsx"
lines_xlsx   = BASE / "2025-11-15-121231-autoload/fish.xlsx"
out_csv      = BASE / "legacy_wrangling_v2/working/legacy_parent_line_overrides_v11.csv"

def norm(s: str) -> str:
    if not s:
        return ""
    s = str(s).strip().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

# --- load unique parent labels ---
df_par = pd.read_excel(parents_xlsx)
parent_labels = sorted({str(x).strip() for x in df_par.iloc[:, 0].dropna() if str(x).strip()})
parent_norms = {pl: norm(pl) for pl in parent_labels}

# --- load line nicknames ---
df_lines = pd.read_excel(lines_xlsx)
if "nickname" not in df_lines.columns:
    raise ValueError("fish.xlsx must have a 'nickname' column")
line_nicks = sorted({str(x).strip() for x in df_lines["nickname"].dropna()})
line_norms = {ln: norm(ln) for ln in line_nicks}

def score(a: str, b: str) -> int:
    """
    Simple fuzzy score:
      +10 if substring
      + token overlap count
    """
    if not a or not b:
        return 0
    sc = 0
    if a in b or b in a:
        sc += 10
    toks_a = set(a.split())
    toks_b = set(b.split())
    sc += len(toks_a & toks_b)
    return sc

rows = []

for pl in parent_labels:
    pn = parent_norms[pl]
    if not pn:
        rows.append({"parent_label": pl, "line_nickname": "", "score": 0})
        continue

    scored = []
    for ln, ln_n in line_norms.items():
        s = score(pn, ln_n)
        if s > 0:
            scored.append((s, ln))

    if not scored:
        best_nick = ""
        best_score = 0
    else:
        scored.sort(reverse=True)
        best_score, best_nick = scored[0]
        if best_score < 2:  # threshold, tune as needed
            best_nick = ""
            best_score = 0

    rows.append({"parent_label": pl, "line_nickname": best_nick, "score": best_score})

df_out = pd.DataFrame(rows)
df_out.to_csv(out_csv, index=False)
print(f"[OK] wrote {len(rows)} rows → {out_csv}")
