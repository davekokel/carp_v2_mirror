# Legacy wrangling v3 — operator runbook (4-person time)

This document answers one question **unambiguously**:

Does this legacy dataset genuinely contain X, or did X leak in from a derived mapping?

If you follow this runbook, the answer will always be clear.

---

## Mental model (read once)

There are exactly **two classes of files**.

### Raw (historical truth)

- Represents what actually existed
- May be messy or inconsistent
- Must never be silently edited
- Lives only in:

seed_kits/legacy_wrangling_v2/raw/

### Derived (disposable)

- Always reproducible
- Safe to delete and regenerate
- Never authoritative
- Lives only in:

seed_kits/legacy_wrangling_v2/working/  
seed_kits/legacy_wrangling_v3/working/

If a value exists **only** in derived files, it is **not evidence of reality**.

---

## Step 0 — ground truth check (raw only)

Before running anything else, check raw inputs:

    rg -n -i 'pswin' seed_kits/legacy_wrangling_v2/raw

Interpretation:

- If pSWIN04 / pSWIN05 appear here → they are real
- If they do not appear here → they must never appear downstream

This is the highest-authority check in the entire pipeline.

---

## Step 1 — delete derived state (safe)

    rm -f seed_kits/legacy_wrangling_v2/working/Unique_parent_names__mom_dad_combined__preview_dqm_from_raw.csv
    rm -f seed_kits/legacy_wrangling_v3/working/legacy_imaging_annotations*.csv

If unsure, deleting the entire working directories is safe.

---

## Step 2 — derive parent map from raw (mandatory)

This step **must always be run**, even if the CSV already exists.

    python - <<'PY'
    import pandas as pd, pathlib

    xlsx = pathlib.Path(
        "seed_kits/legacy_wrangling_v2/raw/"
        "Unique_parent_names__mom_dad_combined__preview_dqm.xlsx"
    )
    out = pathlib.Path(
        "seed_kits/legacy_wrangling_v2/working/"
        "Unique_parent_names__mom_dad_combined__preview_dqm_from_raw.csv"
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    df = pd.read_excel(xlsx, dtype=str)
    df.to_csv(out, index=False)
    print("WROTE", out)
    PY

Rules:

- _v5.csv files are never read
- XLSX → CSV happens fresh on every run
- The working CSV is disposable

---

## Step 3 — run enrichment (single entrypoint)

    python -u seed_kits/legacy_wrangling_v3/scripts/02_enrich.py

Expected results:

- No hard failures
- Two files written:

    legacy_imaging_annotations_v9.csv  
    legacy_imaging_annotations_for_db_v9.csv

---

## Step 4 — invariant check (non-negotiable)

    rg -n -i 'pswin[\- ]?0?4|pswin[\- ]?0?5' \
      seed_kits/legacy_wrangling_v3/working/legacy_imaging_annotations*.csv

Expected outcome:

- **No matches**

If matches exist:

- Stop immediately
- The pipeline is wrong
- Fix the earliest mapping step
- Do **not** patch the database

---

## Step 5 — database load sequence (summary)

Only after Step 4 passes:

1. Load imaging clutch memberships (v9)
2. Link treatments from v9 → v10
3. Seed treated_clutches_v11
4. Seed genotypes from enriched ROI CSV

Each step assumes the invariant already holds.

---

## Step 6 — database truth check

    psql "$DB_URL" -x -c "
    SELECT
      count(*) AS n_clutches,
      count(genotype_v11_id) AS n_with_genotype,
      count(*) - count(genotype_v11_id) AS n_missing
    FROM public.clutches;
    "

Any remaining missing genotypes:

- Must have **zero genotype evidence** in enriched ROI CSV
- Must be documented
- Must not be auto-filled

---

## Historical footnote (why this document exists)

- Unique_parent_names__mom_dad_combined__preview_dqm_v5.csv was a **working artifact**
- It encoded assumptions (for example: pSWIN04 / pSWIN05)
- Treating it as raw caused silent data corruption

This runbook exists to ensure that **cannot happen again**.

---

## One-sentence invariant (memorize this)

If a construct is not present in legacy_wrangling_v2/raw, it is a bug if it appears anywhere else.
