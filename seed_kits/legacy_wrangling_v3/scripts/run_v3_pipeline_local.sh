cd /Users/davekokel/Projects/carp_v2
. .venv/bin/activate
. scripts/use_db.sh
use_local

psql "$DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/20251215_164500_fix_v_roi_overview_all_label_join.sql
psql "$DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/20251215_165500_v_roi_overview_all_label_fallback.sql
psql "$DB_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/20251215_181500_clutches_unique_clutch_code.sql

python seed_kits/legacy_wrangling_v3/scripts/build_v3_roi_biology_map_v1.py
python seed_kits/legacy_wrangling_v3/scripts/diff_v2_vs_v3_genotype_v1.py

python - <<'PY'
import os, hashlib, re
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, text

ROOT = Path("/Users/davekokel/Projects/carp_v2")
V3 = ROOT / "seed_kits" / "legacy_wrangling_v3"
WORK = V3 / "working"
QC = V3 / "qc"
QC.mkdir(parents=True, exist_ok=True)

db_url = os.environ.get("DB_URL")
if not db_url:
    raise SystemExit("DB_URL not set")
eng = create_engine(db_url)

map_csv = WORK / "v3_roi_biology_map_v1.csv"
df = pd.read_csv(map_csv)

no = df[df["v3_fk_resolve_status"] == "no_pairing"].copy()
no = no[no["v3_injected_mgco_codes"].fillna("").astype(str).str.strip() != ""].copy()

codes = sorted(set(sum([c.split("|") for c in no["v3_injected_mgco_codes"].astype(str).tolist()], [])))
codes = [c for c in codes if c]

with eng.begin() as cx:
    rows = cx.execute(text("""
      SELECT construct_code, construct_name, construct_kind
      FROM public.v_constructs_overview
      WHERE construct_code = ANY(:codes)
    """), {"codes": codes}).fetchall()
m = pd.DataFrame(rows, columns=["construct_code","construct_name","construct_kind"])
m["construct_code"] = m["construct_code"].astype(str)

def describe(sig: str) -> str:
    parts = [p for p in str(sig).split("|") if p]
    sub = m[m["construct_code"].isin(parts)].copy().sort_values("construct_code")
    return "; ".join([f"{r.construct_code}={r.construct_name}" for r in sub.itertuples()])

g = (
    no.groupby("experiment_folder", dropna=False)
      .agg(
          n_rows=("bruker_roi_id","count"),
          injected_codes=("v3_injected_mgco_codes", lambda s: "; ".join(sorted(set([x for x in s.astype(str).tolist() if x])))),
      )
      .reset_index()
)

g["injected_constructs"] = g["injected_codes"].apply(describe)
g = g.sort_values(["n_rows","experiment_folder"], ascending=[False, True])
g.to_csv(QC / "no_data_injection_constructs_v1.csv", index=False)

import hashlib
sig_out = WORK / "v3_treatment_signature_map_v1.csv"
df2 = g.copy()

def canon(sig: str) -> str:
    parts = [p.strip() for p in str(sig).split("|") if p.strip()]
    parts = sorted(set(parts))
    return "|".join(parts)

def tcode(sig: str) -> str:
    h = hashlib.sha256(sig.encode("utf-8")).hexdigest()[:8]
    return f"TLEG-{h}"

df2["signature_codes"] = df2["injected_codes"].apply(canon)
df2["treatment_code"] = df2["signature_codes"].apply(tcode)
df2["treatment_text"] = df2["injected_constructs"].fillna("").astype(str)
out_df = df2[["signature_codes","treatment_code","treatment_text"]].drop_duplicates().sort_values("treatment_code")
out_df.to_csv(sig_out, index=False)

mix_out = WORK / "v3_treatment_mix_constructs_v1.csv"
rows = []
for _, r in out_df.iterrows():
    treat_code = r["treatment_code"]
    codes = [c.strip() for c in str(r["signature_codes"]).split("|") if c.strip()]
    for c in codes:
        rows.append({"treat_code": treat_code, "construct_code": c})
mix = pd.DataFrame(rows).drop_duplicates().sort_values(["treat_code","construct_code"])
mix.to_csv(mix_out, index=False)

print("wrote", QC / "no_data_injection_constructs_v1.csv")
print("wrote", sig_out)
print("wrote", mix_out)
PY

python - <<'PY'
import os, pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, text

db_url = os.environ.get("DB_URL")
if not db_url:
    raise SystemExit("DB_URL not set")
eng = create_engine(db_url)

WORK = Path("/Users/davekokel/Projects/carp_v2/seed_kits/legacy_wrangling_v3/working")
df = pd.read_csv(WORK / "v3_treatment_signature_map_v1.csv")

def kind_for(sig: str) -> str:
    sig = str(sig).strip()
    return "injection_single_base" if ("|" not in sig) else "injection"

df["kind_code"] = df["signature_codes"].apply(kind_for)

with eng.begin() as cx:
    ins = text("""
      INSERT INTO public.treatments (treat_code, kind_code, treat_text, source_system, import_batch_id)
      VALUES (:code, :kind, :txt, 'legacy_wrangling_v3', 'legacy_wrangling_v3_tleg_v1')
      ON CONFLICT (treat_code) DO UPDATE
      SET kind_code = EXCLUDED.kind_code,
          treat_text = EXCLUDED.treat_text,
          source_system = EXCLUDED.source_system,
          import_batch_id = EXCLUDED.import_batch_id
    """)
    for _, r in df.iterrows():
        cx.execute(ins, {"code": r["treatment_code"], "kind": r["kind_code"], "txt": r["treatment_text"]})

print("upserted TLEG treatments")
PY

python - <<'PY'
import os
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, text

db_url = os.environ.get("DB_URL")
if not db_url:
    raise SystemExit("DB_URL not set")
eng = create_engine(db_url)

WORK = Path("/Users/davekokel/Projects/carp_v2/seed_kits/legacy_wrangling_v3/working")
mix_csv = WORK / "v3_treatment_mix_constructs_v1.csv"
df = pd.read_csv(mix_csv)

tleg_codes = sorted(df["treat_code"].dropna().astype(str).unique().tolist())

with eng.begin() as cx:
    trows = cx.execute(text("""
      SELECT treat_code, id
      FROM public.treatments
      WHERE treat_code = ANY(:codes)
    """), {"codes": tleg_codes}).fetchall()
    tmap = {r[0]: r[1] for r in trows}

    up_mix = text("""
      INSERT INTO public.treatment_mixes (treatment_id, mix_code, notes)
      VALUES (:tid, 'mix0', :notes)
      ON CONFLICT (treatment_id, mix_code) DO UPDATE
      SET notes = EXCLUDED.notes
    """)
    get_mix = text("""
      SELECT id FROM public.treatment_mixes
      WHERE treatment_id = :tid AND mix_code = 'mix0'
    """)

    mix_id_by_treat = {}
    for treat_code, tid in tmap.items():
        cx.execute(up_mix, {"tid": tid, "notes": f"legacy_wrangling_v3: auto mix0 for {treat_code}"})
        mix_id_by_treat[treat_code] = cx.execute(get_mix, {"tid": tid}).scalar()

    codes = sorted(df["construct_code"].dropna().astype(str).unique().tolist())
    crows = cx.execute(text("""
      SELECT construct_code, id
      FROM public.constructs
      WHERE construct_code = ANY(:codes)
    """), {"codes": codes}).fetchall()
    cmap = {r[0]: r[1] for r in crows}

    cx.execute(text("""
      DELETE FROM public.treatment_mix_constructs
      WHERE mix_id = ANY(:mix_ids)
    """), {"mix_ids": list(mix_id_by_treat.values())})

    ins = text("""
      INSERT INTO public.treatment_mix_constructs (mix_id, construct_id, role, notes)
      VALUES (:mix_id, :construct_id, 'legacy_injection', :notes)
    """)
    for _, r in df.iterrows():
        cx.execute(ins, {
            "mix_id": mix_id_by_treat[r["treat_code"]],
            "construct_id": cmap[r["construct_code"]],
            "notes": f"legacy_wrangling_v3 {r['treat_code']}",
        })

print("upserted treatment_mixes + mix_constructs")
PY

python - <<'PY'
import os
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, text

db_url = os.environ.get("DB_URL")
if not db_url:
    raise SystemExit("DB_URL not set")
eng = create_engine(db_url)

V3 = Path("/Users/davekokel/Projects/carp_v2/seed_kits/legacy_wrangling_v3")
QC = V3 / "qc"
WORK = V3 / "working"

exp_map = pd.read_csv(QC / "no_data_injection_constructs_v1.csv")
sig_map = pd.read_csv(WORK / "v3_treatment_signature_map_v1.csv")

def canon(sig: str) -> str:
    parts = [p.strip() for p in str(sig).split("|") if p.strip()]
    parts = sorted(set(parts))
    return "|".join(parts)

exp_map["signature_codes"] = exp_map["injected_codes"].apply(canon)
sig_map["signature_codes"] = sig_map["signature_codes"].apply(canon)
m = exp_map.merge(sig_map[["signature_codes","treatment_code"]], on="signature_codes", how="left")

with eng.begin() as cx:
    trows = cx.execute(text("""
      SELECT treat_code, id
      FROM public.treatments
      WHERE treat_code = ANY(:codes)
    """), {"codes": m["treatment_code"].tolist()}).fetchall()
    tmap = {r[0]: r[1] for r in trows}

    slots = cx.execute(text("""
      SELECT
        p.experiment_name,
        s.id AS slot_id,
        c.id AS clutch_id,
        c.clutch_code,
        icm.treated_clutch_id
      FROM public.imaging_plates p
      JOIN public.imaging_slots s ON s.plate_id = p.id
      JOIN public.imaging_clutch_memberships icm ON icm.slot_id = s.id
      JOIN public.clutches c ON c.id = icm.clutch_id
      WHERE p.experiment_name = ANY(:exp_names)
    """), {"exp_names": m["experiment_folder"].tolist()}).fetchall()

    df_slots = pd.DataFrame(slots, columns=["experiment_name","slot_id","clutch_id","clutch_code","treated_clutch_id"])

    get_existing = text("""
      SELECT id
      FROM public.treated_clutches_v11
      WHERE clutch_id = :clutch_id AND treatment_id = :treatment_id
      LIMIT 1
    """)
    get_max_suffix = text("""
      SELECT max(right(treated_clutch_code, 2))::int
      FROM public.treated_clutches_v11
      WHERE treated_clutch_code LIKE :prefix
    """)
    ins_tc = text("""
      INSERT INTO public.treated_clutches_v11 (clutch_id, treated_clutch_code, treatment_id, created_by, notes)
      VALUES (:clutch_id, :code, :treatment_id, 'legacy_wrangling_v3', :notes)
      ON CONFLICT (treated_clutch_code) DO NOTHING
      RETURNING id
    """)
    upd_icm = text("""
      UPDATE public.imaging_clutch_memberships
      SET treated_clutch_id = :tc_id
      WHERE slot_id = :slot_id
    """)

    for exp_name, grp in df_slots.groupby("experiment_name"):
        treat_code = m.loc[m["experiment_folder"] == exp_name, "treatment_code"].iloc[0]
        treatment_id = tmap[treat_code]

        for r in grp.itertuples(index=False):
            if pd.notna(r.treated_clutch_id):
                continue
            ex = cx.execute(get_existing, {"clutch_id": r.clutch_id, "treatment_id": treatment_id}).fetchone()
            if ex:
                tc_id = ex[0]
            else:
                prefix = f"TREAT-{r.clutch_code}-"
                mx = cx.execute(get_max_suffix, {"prefix": prefix + "%"}).scalar()
                nxt = 0 if mx is None else int(mx) + 1
                code = f"{prefix}{nxt:02d}"
                notes = f"v3 auto from experiment={exp_name} treat_code={treat_code} signature={canon(m.loc[m['experiment_folder']==exp_name,'injected_codes'].iloc[0])}"
                tc_id = cx.execute(ins_tc, {"clutch_id": r.clutch_id, "code": code, "treatment_id": treatment_id, "notes": notes}).scalar()
                if tc_id is None:
                    tc_id = cx.execute(get_existing, {"clutch_id": r.clutch_id, "treatment_id": treatment_id}).scalar()
            cx.execute(upd_icm, {"tc_id": tc_id, "slot_id": r.slot_id})

print("linked treated_clutches into imaging_clutch_memberships")
PY

psql "$DB_URL" -Atc "
WITH base AS (
  SELECT tc.id AS treated_clutch_id, cg.id AS clutch_genotype_id
  FROM public.treated_clutches_v11 tc
  JOIN public.clutch_genotypes_v11 cg ON cg.clutch_id = tc.clutch_id
  WHERE cg.is_enabled IS TRUE
),
missing AS (
  SELECT b.*
  FROM base b
  LEFT JOIN public.treated_clutch_genotypes_v11 t
    ON t.treated_clutch_id = b.treated_clutch_id
   AND t.clutch_genotype_id = b.clutch_genotype_id
  WHERE t.treated_clutch_id IS NULL
),
ranked AS (
  SELECT treated_clutch_id, clutch_genotype_id,
         row_number() OVER (PARTITION BY treated_clutch_id ORDER BY clutch_genotype_id) AS rn
  FROM missing
)
INSERT INTO public.treated_clutch_genotypes_v11 (treated_clutch_id, clutch_genotype_id, is_primary)
SELECT treated_clutch_id, clutch_genotype_id, (rn = 1) AS is_primary
FROM ranked;
"

psql "$DB_URL" -Atc "
SELECT
  (SELECT count(*) FROM imaging_roi_annotations) AS n_rois,
  (SELECT count(*) FROM v_roi_overview_all) AS n_v_roi_overview_all;
"

psql "$DB_URL" -Atc "
SELECT
  sum((label_tg_style IS NULL)::int) AS label_tg_style_null
FROM public.v_roi_overview_all;
"
