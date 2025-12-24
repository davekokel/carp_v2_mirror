#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

PARENT_XLSX = REPO / "seed_kits" / "legacy_wrangling_v2" / "raw" / "Unique_parent_names__mom_dad_combined__preview_dqm.xlsx"
PARENT_CSV  = REPO / "seed_kits" / "legacy_wrangling_v2" / "working" / "Unique_parent_names__mom_dad_combined__preview_dqm_from_raw.csv"

def run(cmd: list[str]) -> None:
    print("\n[RUN]", " ".join(cmd))
    subprocess.run(cmd, check=True)

def require_env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise SystemExit(f"[STOP] {name} must be set")
    return v

def ensure_parent_map_csv() -> None:
    if PARENT_CSV.exists():
        return
    if not PARENT_XLSX.exists():
        raise SystemExit(f"[STOP] missing parent XLSX: {PARENT_XLSX}")

    PARENT_CSV.parent.mkdir(parents=True, exist_ok=True)

    code = (
        "import pandas as pd\n"
        f"p_in = r'''{PARENT_XLSX}'''\n"
        f"p_out = r'''{PARENT_CSV}'''\n"
        "df = pd.read_excel(p_in, dtype=str)\n"
        "df.columns = [str(c).strip() for c in df.columns]\n"
        "df.to_csv(p_out, index=False)\n"
        "print('WROTE', p_out, 'ROWS', len(df))\n"
    )
    run(["python", "-c", code])

def assert_transgene_alleles_exist() -> None:
    code = (
        "import os\n"
        "from sqlalchemy import create_engine, text\n"
        "url=os.environ.get('DB_URL')\n"
        "eng=create_engine(url)\n"
        "with eng.begin() as cx:\n"
        "  n = cx.execute(text('select count(*) from public.transgene_alleles')).scalar()\n"
        "n = int(n or 0)\n"
        "print('TRANS_GENE_ALLELES_ROWS', n)\n"
        "if n == 0:\n"
        "  raise SystemExit('[STOP] public.transgene_alleles is empty; run foundation pipeline first')\n"
    )
    run(["python", "-c", code])

def main() -> None:
    require_env("DB_URL")
    print("[DB_URL]", os.environ["DB_URL"])

    ensure_parent_map_csv()

    run(["python", "scripts/foundation_run_pipeline.py"])
    assert_transgene_alleles_exist()

    run(["python", "scripts/legacy_imaging_run_pipeline.py"])

    run(["python", "scripts/v10_seed_construct_aliases_from_constructs.py"])
    run(["python", "scripts/v11_build_exp_treatment_signatures_with_basecodes.py"])
    run(["python", "scripts/v11_autofill_exp_treatment_token_map.py"])
    run(["python", "scripts/v11_expand_exp_treatment_dataset_overrides.py"])
    run(["python", "scripts/v11_apply_exp_treatment_signatures_csv.py"])
    run(["python", "scripts/v11_apply_free_text_label_treatments.py"])
    run(["python", "scripts/v11_frontfill_imaging_clutch_memberships_treated.py"])

    run(["python", "scripts/v11_qc_legacy_imaging_treatments.py"])
    print("\n[OK] full local load pipeline completed cleanly")

if __name__ == "__main__":
    main()
