from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT / "seed_kits" / "2025-11-15-121231-autoload"

PLASMIDS_CSV        = SEED_DIR / "plasmids.csv"
PLASMID_FUSIONS_CSV = SEED_DIR / "plasmid_fusions.csv"
RNA_FUSIONS_CSV     = SEED_DIR / "rna_fusions.csv"
OUT_CSV             = SEED_DIR / "constructs_plasmid.csv"


def _pick_code_column(df: pd.DataFrame, candidates: list[str], context: str) -> str:
    """Find the first existing column from candidates and return its name."""
    for c in candidates:
        if c in df.columns:
            return c
    raise ValueError(
        f"{context} must have one of these columns for the base/code: {candidates}, but has: {list(df.columns)}"
    )


def main() -> None:
    if not PLASMIDS_CSV.exists():
        raise FileNotFoundError(f"plasmids.csv not found: {PLASMIDS_CSV}")
    if not PLASMID_FUSIONS_CSV.exists():
        raise FileNotFoundError(f"plasmid_fusions.csv not found: {PLASMID_FUSIONS_CSV}")

    df_p = pd.read_csv(PLASMIDS_CSV)
    df_f = pd.read_csv(PLASMID_FUSIONS_CSV)

    # ───────── Plasmids metadata ─────────
    df_p = df_p.copy()
    df_p.columns = [c.strip().lower() for c in df_p.columns]

    code_col_p = _pick_code_column(
        df_p,
        candidates=["plasmid_base_code", "plasmid_code", "code", "base_code"],
        context="plasmids.csv",
    )
    df_p["plasmid_code"] = df_p[code_col_p].astype(str).str.strip()

    for col in ["nickname", "resistance", "notes"]:
        if col not in df_p.columns:
            df_p[col] = ""

    df_p["nickname"] = df_p["nickname"].fillna("")
    df_p["resistance"] = df_p["resistance"].fillna("")
    df_p["notes"] = df_p["notes"].fillna("")

    plasmid_meta = df_p[["plasmid_code", "nickname", "resistance", "notes"]].rename(
        columns={
            "nickname": "plasmid_nickname",
            "resistance": "resistance",
            "notes": "plasmid_notes",
        }
    )

    # ───────── Plasmid fusions ─────────
    df_f = df_f.copy()
    df_f.columns = [c.strip().lower() for c in df_f.columns]

    code_col_f = _pick_code_column(
        df_f,
        candidates=["plasmid_base_code", "plasmid_code", "code", "base_code"],
        context="plasmid_fusions.csv",
    )
    df_f["plasmid_code"] = df_f[code_col_f].astype(str).str.strip()

    required_f_cols = ["plasmid_name", "n_fluors_per_plasmid", "fluor", "tag", "tag_pos"]
    for col in required_f_cols:
        if col not in df_f.columns:
            raise ValueError(f"plasmid_fusions.csv missing required column: {col}")

    # Right-join so every plasmid appears at least once (even if it has no fusions)
    merged = df_f.merge(df_p, on="plasmid_code", how="right", suffixes=("", "_p"))

    merged = merged.copy()
    for col in ["plasmid_name", "fluor", "tag", "tag_pos", "nickname", "resistance", "notes"]:
        if col in merged.columns:
            merged[col] = merged[col].fillna("")

    def _fmt_n(x):
        if pd.isna(x):
            return ""
        try:
            return str(int(x))
        except Exception:
            return str(x)

    merged["n_fluors_per_plasmid"] = merged["n_fluors_per_plasmid"].apply(_fmt_n)

    merged["used_for_injection_plasmid"] = "false"
    merged["used_for_injection_rna"] = "false"
    merged["used_for_injection_crispr"] = "false"

    final = merged[[
        "plasmid_code",
        "plasmid_name",
        "nickname",
        "resistance",
        "notes",
        "used_for_injection_plasmid",
        "used_for_injection_rna",
        "used_for_injection_crispr",
        "n_fluors_per_plasmid",
        "fluor",
        "tag",
        "tag_pos",
    ]].copy()

    final.columns = [
        "plasmid_code",
        "plasmid_name",
        "plasmid_nickname",
        "resistance",
        "plasmid_notes",
        "used_for_injection_plasmid",
        "used_for_injection_rna",
        "used_for_injection_crispr",
        "n_fluors_per_plasmid",
        "fluor_code",
        "tag_code",
        "tag_pos",
    ]

    # ───────── Append RNA-based fusions ─────────
    if RNA_FUSIONS_CSV.exists():
        df_rf = pd.read_csv(RNA_FUSIONS_CSV)
        df_rf = df_rf.copy()
        df_rf.columns = [c.strip().lower() for c in df_rf.columns]

        try:
            code_col_rf = _pick_code_column(
                df_rf,
                candidates=["rna_base_code", "rna_code", "plasmid_base_code", "code", "base_code"],
                context="rna_fusions.csv",
            )
        except ValueError as e:
            print(f"[WARN] {e} — skipping RNA fusions append.")
            code_col_rf = None

        if code_col_rf is not None:
            df_rf["plasmid_code"] = df_rf[code_col_rf].astype(str).str.strip()

            # Ensure fluor/tag/tag_pos columns exist
            for col in ["fluor", "tag", "tag_pos"]:
                if col not in df_rf.columns:
                    df_rf[col] = ""
                df_rf[col] = df_rf[col].fillna("")

            # Merge with plasmid metadata (may be missing for some constructs)
            df_rf_meta = df_rf.merge(plasmid_meta, on="plasmid_code", how="left")

            # Ensure metadata columns exist
            for col in ["plasmid_name", "plasmid_nickname", "plasmid_notes", "resistance"]:
                if col not in df_rf_meta.columns:
                    df_rf_meta[col] = ""
                df_rf_meta[col] = df_rf_meta[col].fillna("")

            # Try to use RNA name as fallback name/nickname for constructs that exist only in RNA
            name_col_rf = None
            for c in ["rna_name", "name", "nickname"]:
                if c in df_rf_meta.columns:
                    name_col_rf = c
                    break

            if name_col_rf is not None:
                name_series = df_rf_meta[name_col_rf].astype(str).fillna("")
                mask_missing_name = df_rf_meta["plasmid_name"] == ""
                df_rf_meta.loc[mask_missing_name, "plasmid_name"] = name_series[mask_missing_name]
                mask_missing_nick = df_rf_meta["plasmid_nickname"] == ""
                df_rf_meta.loc[mask_missing_nick, "plasmid_nickname"] = name_series[mask_missing_nick]

            # Build rows compatible with 'final'
            df_rf_out = pd.DataFrame({
                "plasmid_code": df_rf_meta["plasmid_code"],
                "plasmid_name": df_rf_meta["plasmid_name"],
                "plasmid_nickname": df_rf_meta["plasmid_nickname"],
                "resistance": df_rf_meta["resistance"],
                "plasmid_notes": df_rf_meta["plasmid_notes"],
                "used_for_injection_plasmid": "false",
                "used_for_injection_rna": "false",
                "used_for_injection_crispr": "false",
                "n_fluors_per_plasmid": "",  # hint not used for RNA-derived rows
                "fluor_code": df_rf_meta["fluor"],
                "tag_code": df_rf_meta["tag"],
                "tag_pos": df_rf_meta["tag_pos"],
            })

            # Append and drop duplicate fusions per construct
            combined = pd.concat([final, df_rf_out], ignore_index=True)
            combined = combined.drop_duplicates(
                subset=["plasmid_code", "fluor_code", "tag_code", "tag_pos"],
                keep="first",
            )
            final = combined

    final.to_csv(OUT_CSV, index=False)
    print(f"Wrote {len(final)} rows to {OUT_CSV}")

if __name__ == "__main__":
    main()
