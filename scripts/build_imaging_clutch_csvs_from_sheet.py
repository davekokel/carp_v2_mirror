#!/usr/bin/env python
from __future__ import annotations

import argparse
import pathlib
from typing import List, Tuple

import pandas as pd


def _norm_col(c: str) -> str:
    return c.strip().lower()


def _find_col(df: pd.DataFrame, candidates: List[str]) -> str | None:
    cols = {_norm_col(c): c for c in df.columns}
    for logical in candidates:
        if logical in cols:
            return cols[logical]
    return None


def _split_tokens(value: object) -> List[str]:
    if value is None:
        return []
    text = str(value)
    out: List[str] = []
    for raw in text.split(","):
        for t in str(raw).split(";"):
            t = t.strip()
            if not t or t.lower() == "nan":
                continue
            out.append(t)
    return out


def _build_genotype_fields(
    female_base: str | float | None,
    female_allele: str | float | None,
    male_base: str | float | None,
    male_allele: str | float | None,
) -> Tuple[str, str, str, str]:
    pairs = []

    if pd.notna(female_base) and pd.notna(female_allele):
        pairs.append((str(female_base), str(female_allele)))
    if pd.notna(male_base) and pd.notna(male_allele):
        pairs.append((str(male_base), str(male_allele)))

    if not pairs:
        return "", "", "", ""

    unique_pairs = []
    seen = set()
    for base, allele in pairs:
        key = (base, allele)
        if key not in seen:
            seen.add(key)
            unique_pairs.append((base, allele))

    bases = sorted({base for base, _ in unique_pairs})
    genotype_base_codes = ",".join(bases)

    allele_codes = [f"{base}:{allele}" for base, allele in unique_pairs]
    genotype_allele_codes = ",".join(allele_codes)

    pretty_parts = [f"{base}({allele})" for base, allele in unique_pairs]
    genotype_pretty = "/".join(pretty_parts)

    base_for_label = bases[0]
    alleles_sorted = sorted({allele for _, allele in unique_pairs})
    genotype_cross_label = base_for_label + "_" + "_".join(alleles_sorted)

    return (
        genotype_base_codes,
        genotype_allele_codes,
        genotype_pretty,
        genotype_cross_label,
    )


def build_clutch_csvs(sheet_path: pathlib.Path, out_dir: pathlib.Path) -> None:
    if not sheet_path.exists():
        raise FileNotFoundError(f"Imaging sheet not found: {sheet_path}")

    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_excel(sheet_path)

    female_col = _find_col(df, ["zf female genotype", "zf_female_genotype"])
    male_col = _find_col(df, ["zf male genotype", "zf_male_genotype"])
    date_born_col = _find_col(df, ["date born", "date_born", "birthday"])
    data_loc_col = _find_col(df, ["data location", "data_location", "data path"])
    date_mount_col = _find_col(df, ["date_mount", "date mount"])
    mount_id_col = _find_col(df, ["mount_id", "mount id"])
    inj_plasmid_col = _find_col(df, ["additional plasmids injected"])
    inj_mrna_col = _find_col(df, ["additional mrnas injected"])
    inj_protein_col = _find_col(df, ["additonal proteins injected"])
    inj_dye_col = _find_col(df, ["additonal dye and chemicals"])

    missing = []
    if date_born_col is None:
        missing.append("Date born")
    if female_col is None:
        missing.append("ZF female genotype")
    if male_col is None:
        missing.append("ZF male genotype")
    if missing:
        raise RuntimeError(
            "Missing required columns in imaging sheet: "
            + ", ".join(missing)
            + f"\nColumns present: {list(df.columns)}"
        )

    df["sheet_row_index"] = df.index + 1
    df_valid = df[df[date_born_col].notna()].copy()
    df_valid[date_born_col] = pd.to_datetime(df_valid[date_born_col]).dt.date

    group_cols = [date_born_col, female_col, male_col]

    groups = (
        df_valid.groupby(group_cols, dropna=False)
        .size()
        .reset_index(name="n_fish")
        .sort_values(by=[date_born_col, female_col, male_col])
    )

    groups["clutch_idx_for_date"] = (
        groups.groupby(date_born_col).cumcount() + 1
    )

    def _make_clutch_code(row: pd.Series) -> str:
        date_str = row[date_born_col].strftime("%Y%m%d")
        idx = int(row["clutch_idx_for_date"])
        return f"IMG_CLT_{date_str}_{idx:02d}"

    groups["clutch_code"] = groups.apply(_make_clutch_code, axis=1)

    clutches = pd.DataFrame(
        {
            "clutch_code": groups["clutch_code"],
            "clutch_date": groups[date_born_col],
            "estimated_egg_count": groups["n_fish"],
            "source_system": "imaging_backfill",
            "female_genotype_text": groups[female_col],
            "male_genotype_text": groups[male_col],
            "notes": (
                "Backfilled from imaging_sheet; "
                "grouped by (Date born, ZF female genotype, ZF male genotype)"
            ),
        }
    )

    parents_path = sheet_path.parent / "Unique_parent_names__mom_dad_combined__preview_dqm.xlsx"
    if parents_path.exists():
        parents = pd.read_excel(parents_path)
        required_cols = {"parent_fish_name", "plasmid_base_code", "allele"}
        if required_cols.issubset(parents.columns):
            parents = parents.copy()
            parents["parent_key"] = parents["parent_fish_name"].astype(str).str.strip().str.lower()

            clutches["female_key"] = clutches["female_genotype_text"].astype(str).str.strip().str.lower()
            clutches["male_key"] = clutches["male_genotype_text"].astype(str).str.strip().str.lower()

            f_map = parents[["parent_key", "plasmid_base_code", "allele"]].rename(
                columns={
                    "plasmid_base_code": "female_plasmid_base_code",
                    "allele": "female_allele",
                }
            )
            m_map = parents[["parent_key", "plasmid_base_code", "allele"]].rename(
                columns={
                    "plasmid_base_code": "male_plasmid_base_code",
                    "allele": "male_allele",
                }
            )

            clutches = clutches.merge(
                f_map, how="left", left_on="female_key", right_on="parent_key"
            )
            clutches = clutches.merge(
                m_map, how="left", left_on="male_key", right_on="parent_key"
            )

            to_drop = [
                c
                for c in ["female_key", "male_key", "parent_key_x", "parent_key_y"]
                if c in clutches.columns
            ]
            if to_drop:
                clutches = clutches.drop(columns=to_drop)
        else:
            print(
                f"[WARN] Parent mapping file {parents_path} missing expected columns; "
                "skipping plasmid/allele enrichment."
            )
    else:
        print(
            f"[WARN] Parent mapping file not found at {parents_path}; "
            "skipping plasmid/allele enrichment."
        )

    # Build clutch-level genotype summary fields
    (
        genotype_base_codes_list,
        genotype_allele_codes_list,
        genotype_pretty_list,
        genotype_cross_label_list,
    ) = ([], [], [], [])

    for _, row in clutches.iterrows():
        f_base = row.get("female_plasmid_base_code")
        f_alle = row.get("female_allele")
        m_base = row.get("male_plasmid_base_code")
        m_alle = row.get("male_allele")
        gb, ga, gp, gl = _build_genotype_fields(f_base, f_alle, m_base, m_alle)
        genotype_base_codes_list.append(gb)
        genotype_allele_codes_list.append(ga)
        genotype_pretty_list.append(gp)
        genotype_cross_label_list.append(gl)

    clutches["genotype_base_codes"] = genotype_base_codes_list
    clutches["genotype_allele_codes"] = genotype_allele_codes_list
    clutches["genotype_pretty"] = genotype_pretty_list
    clutches["genotype_cross_label"] = genotype_cross_label_list

    # Roll up treatments (text) at clutch level
    df_merge_clutch = df_valid.merge(
        groups[group_cols + ["clutch_code"]],
        on=group_cols,
        how="left",
        validate="many_to_one",
    )

    def _rollup(col_name: str | None) -> dict[str, str]:
        if col_name is None:
            return {}
        sub = df_merge_clutch[["clutch_code", col_name]].dropna()
        result: dict[str, str] = {}
        for clutch_code, rows in sub.groupby("clutch_code"):
            tokens: List[str] = []
            for v in rows[col_name]:
                tokens.extend(_split_tokens(v))
            uniq = []
            seen = set()
            for t in tokens:
                if t not in seen:
                    seen.add(t)
                    uniq.append(t)
            result[clutch_code] = "; ".join(uniq)
        return result

    plasmid_roll = _rollup(inj_plasmid_col)
    mrna_roll = _rollup(inj_mrna_col)
    protein_roll = _rollup(inj_protein_col)
    dye_roll = _rollup(inj_dye_col)

    clutches["treatment_plasmids_text"] = clutches["clutch_code"].map(plasmid_roll).fillna("")
    clutches["treatment_rnas_text"] = clutches["clutch_code"].map(mrna_roll).fillna("")
    clutches["treatment_proteins_text"] = clutches["clutch_code"].map(protein_roll).fillna("")
    clutches["treatment_dyes_text"] = clutches["clutch_code"].map(dye_roll).fillna("")

    clutches_path = out_dir / "imaging_clutches_from_sheet_draft.csv"
    clutches.to_csv(clutches_path, index=False)

    # Membership CSV: include raw per-row treatments
    df_merge = df_valid.merge(
        groups[group_cols + ["clutch_code"]],
        on=group_cols,
        how="left",
        validate="many_to_one",
    )

    membership_cols = [
        "clutch_code",
        "sheet_row_index",
        date_born_col,
        female_col,
        male_col,
    ]
    if date_mount_col is not None:
        membership_cols.append(date_mount_col)
    if mount_id_col is not None:
        membership_cols.append(mount_id_col)
    if data_loc_col is not None:
        membership_cols.append(data_loc_col)
    if inj_plasmid_col is not None:
        membership_cols.append(inj_plasmid_col)
    if inj_mrna_col is not None:
        membership_cols.append(inj_mrna_col)
    if inj_protein_col is not None:
        membership_cols.append(inj_protein_col)
    if inj_dye_col is not None:
        membership_cols.append(inj_dye_col)

    memberships = df_merge[membership_cols].copy()

    rename_map = {
        date_born_col: "date_born",
        female_col: "zf_female_genotype_text",
        male_col: "zf_male_genotype_text",
    }
    if date_mount_col is not None:
        rename_map[date_mount_col] = "date_mount"
    if mount_id_col is not None:
        rename_map[mount_id_col] = "mount_id"
    if data_loc_col is not None:
        rename_map[data_loc_col] = "data_location"
    if inj_plasmid_col is not None:
        rename_map[inj_plasmid_col] = "row_plasmids_text"
    if inj_mrna_col is not None:
        rename_map[inj_mrna_col] = "row_rnas_text"
    if inj_protein_col is not None:
        rename_map[inj_protein_col] = "row_proteins_text"
    if inj_dye_col is not None:
        rename_map[inj_dye_col] = "row_dyes_text"

    memberships = memberships.rename(columns=rename_map)

    memberships_path = out_dir / "imaging_clutch_memberships_from_sheet_draft.csv"
    memberships.to_csv(memberships_path, index=False)

    print(f"[OK] Wrote {len(clutches)} clutches → {clutches_path}")
    print(f"[OK] Wrote {len(memberships)} memberships → {memberships_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build imaging clutch CSVs from imaging_sheet.xlsx "
            "without any DB dependencies."
        )
    )
    parser.add_argument(
        "--sheet",
        type=pathlib.Path,
        default=pathlib.Path(
            "seed_kits/legacy_import/raw/2025-11-13-124226-imaging_sheet.xlsx"
        ),
        help="Path to imaging_sheet.xlsx",
    )
    parser.add_argument(
        "--out-dir",
        type=pathlib.Path,
        default=pathlib.Path("seed_kits/legacy_import/working"),
        help="Directory to write draft clutch CSVs into",
    )
    args = parser.parse_args()
    build_clutch_csvs(args.sheet, args.out_dir)


if __name__ == "__main__":
    main()
