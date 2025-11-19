#!/usr/bin/env python
from __future__ import annotations

import argparse
import pathlib
from typing import Dict, List, Tuple

import pandas as pd


def _split_tokens(text: object) -> List[str]:
    if text is None:
        return []
    s = str(text)
    out: List[str] = []
    for chunk in s.replace(";", ",").split(","):
        t = chunk.strip()
        if not t or t.lower() == "nan":
            continue
        out.append(t)
    return out


def _build_mapping_from_preview(path: pathlib.Path, text_col: str, base_col: str) -> Dict[str, List[str]]:
    """
    Build mapping: normalized text token -> list of plasmid_base_code(s),
    using a preview sheet like Unique_injected_plasmid__preview_dqm.xlsx.
    """
    if not path.exists():
        raise FileNotFoundError(f"Preview mapping file not found: {path}")

    df = pd.read_excel(path)
    if text_col not in df.columns or base_col not in df.columns:
        raise RuntimeError(
            f"{path} missing expected columns: {text_col}, {base_col}; "
            f"columns present: {list(df.columns)}"
        )

    mapping: Dict[str, List[str]] = {}
    for _, row in df.iterrows():
        raw_label = str(row[text_col])
        norm = raw_label.strip().lower()
        base_val = row[base_col]
        if pd.isna(base_val):
            continue
        base_codes = []
        for part in str(base_val).replace(";", ",").split(","):
            t = part.strip()
            if t:
                base_codes.append(t)
        if not base_codes:
            continue
        mapping.setdefault(norm, [])
        for b in base_codes:
            if b not in mapping[norm]:
                mapping[norm].append(b)
    return mapping


def build_treatments(
    clutches_csv: pathlib.Path,
    plasmid_preview: pathlib.Path,
    rna_preview: pathlib.Path,
    out_dir: pathlib.Path,
) -> None:
    if not clutches_csv.exists():
        raise FileNotFoundError(f"Clutches CSV not found: {clutches_csv}")
    out_dir.mkdir(parents=True, exist_ok=True)

    clutches = pd.read_csv(clutches_csv)

    for needed in [
        "clutch_code",
        "treatment_plasmids_text",
        "treatment_rnas_text",
        "treatment_proteins_text",
        "treatment_dyes_text",
    ]:
        if needed not in clutches.columns:
            raise RuntimeError(
                f"{clutches_csv} missing expected column '{needed}'. "
                f"Columns present: {list(clutches.columns)}"
            )

    plasmid_map = _build_mapping_from_preview(
        plasmid_preview, text_col="injected_plasmid", base_col="plasmid_base_code"
    )
    rna_map = _build_mapping_from_preview(
        rna_preview, text_col="injected_rna", base_col="plasmid_base_code"
    )

    rows: List[Dict[str, object]] = []
    signatures: Dict[str, str] = {}  # signature -> treatment_code

    for _, row in clutches.iterrows():
        clutch_code = row["clutch_code"]

        plasmid_tokens = _split_tokens(row["treatment_plasmids_text"])
        rna_tokens = _split_tokens(row["treatment_rnas_text"])
        protein_tokens = _split_tokens(row["treatment_proteins_text"])
        dye_tokens = _split_tokens(row["treatment_dyes_text"])

        mapped_bases: List[str] = []
        unmapped_plasmids: List[str] = []
        unmapped_rnas: List[str] = []

        for tok in plasmid_tokens:
            key = tok.strip().lower()
            if key in plasmid_map:
                for b in plasmid_map[key]:
                    if b not in mapped_bases:
                        mapped_bases.append(b)
            else:
                unmapped_plasmids.append(tok)

        for tok in rna_tokens:
            key = tok.strip().lower()
            if key in rna_map:
                for b in rna_map[key]:
                    if b not in mapped_bases:
                        mapped_bases.append(b)
            else:
                unmapped_rnas.append(tok)

        mapped_bases_sorted = sorted(mapped_bases)
        plasmid_tokens_sorted = sorted(plasmid_tokens)
        rna_tokens_sorted = sorted(rna_tokens)
        protein_tokens_sorted = sorted(protein_tokens)
        dye_tokens_sorted = sorted(dye_tokens)
        unmapped_plasmids_sorted = sorted(set(unmapped_plasmids))
        unmapped_rnas_sorted = sorted(set(unmapped_rnas))

        signature_parts: List[str] = []
        if mapped_bases_sorted:
            signature_parts.append("bases=" + "|".join(mapped_bases_sorted))
        if plasmid_tokens_sorted:
            signature_parts.append("plasmids=" + "|".join(plasmid_tokens_sorted))
        if rna_tokens_sorted:
            signature_parts.append("rnas=" + "|".join(rna_tokens_sorted))
        if protein_tokens_sorted:
            signature_parts.append("proteins=" + "|".join(protein_tokens_sorted))
        if dye_tokens_sorted:
            signature_parts.append("dyes=" + "|".join(dye_tokens_sorted))

        signature = ";;".join(signature_parts)

        if signature not in signatures:
            treatment_code = f"IMG_TRT_{len(signatures) + 1:03d}"
            signatures[signature] = treatment_code
            rows.append(
                {
                    "treatment_code": treatment_code,
                    "source_system": "imaging_backfill",
                    "plasmid_base_codes": ",".join(mapped_bases_sorted),
                    "plasmid_tokens_raw": "; ".join(plasmid_tokens_sorted),
                    "rna_tokens_raw": "; ".join(rna_tokens_sorted),
                    "protein_tokens_raw": "; ".join(protein_tokens_sorted),
                    "dye_tokens_raw": "; ".join(dye_tokens_sorted),
                    "unmapped_plasmid_tokens": "; ".join(unmapped_plasmids_sorted),
                    "unmapped_rna_tokens": "; ".join(unmapped_rnas_sorted),
                }
            )

    treatments_df = pd.DataFrame(rows).sort_values("treatment_code")
    treatments_path = out_dir / "imaging_treatments_from_sheet_draft.csv"
    treatments_df.to_csv(treatments_path, index=False)

    clutch_treatments = []
    for _, row in clutches.iterrows():
        clutch_code = row["clutch_code"]
        plasmid_tokens = _split_tokens(row["treatment_plasmids_text"])
        rna_tokens = _split_tokens(row["treatment_rnas_text"])
        protein_tokens = _split_tokens(row["treatment_proteins_text"])
        dye_tokens = _split_tokens(row["treatment_dyes_text"])

        mapped_bases: List[str] = []
        unmapped_plasmids: List[str] = []
        unmapped_rnas: List[str] = []

        for tok in plasmid_tokens:
            key = tok.strip().lower()
            if key in plasmid_map:
                for b in plasmid_map[key]:
                    if b not in mapped_bases:
                        mapped_bases.append(b)
            else:
                unmapped_plasmids.append(tok)

        for tok in rna_tokens:
            key = tok.strip().lower()
            if key in rna_map:
                for b in rna_map[key]:
                    if b not in mapped_bases:
                        mapped_bases.append(b)
            else:
                unmapped_rnas.append(tok)

        mapped_bases_sorted = sorted(mapped_bases)
        plasmid_tokens_sorted = sorted(plasmid_tokens)
        rna_tokens_sorted = sorted(rna_tokens)
        protein_tokens_sorted = sorted(protein_tokens)
        dye_tokens_sorted = sorted(dye_tokens)

        signature_parts: List[str] = []
        if mapped_bases_sorted:
            signature_parts.append("bases=" + "|".join(mapped_bases_sorted))
        if plasmid_tokens_sorted:
            signature_parts.append("plasmids=" + "|".join(plasmid_tokens_sorted))
        if rna_tokens_sorted:
            signature_parts.append("rnas=" + "|".join(rna_tokens_sorted))
        if protein_tokens_sorted:
            signature_parts.append("proteins=" + "|".join(protein_tokens_sorted))
        if dye_tokens_sorted:
            signature_parts.append("dyes=" + "|".join(dye_tokens_sorted))
        signature = ";;".join(signature_parts)

        treatment_code = signatures.get(signature)
        clutch_treatments.append(
            {
                "clutch_code": clutch_code,
                "treatment_code": treatment_code,
            }
        )

    clutch_treatments_df = pd.DataFrame(clutch_treatments).sort_values(
        ["clutch_code", "treatment_code"]
    )
    clutch_treatments_path = out_dir / "imaging_clutch_treatments_from_sheet_draft.csv"
    clutch_treatments_df.to_csv(clutch_treatments_path, index=False)

    print(f"[OK] Wrote {len(treatments_df)} treatments → {treatments_path}")
    print(f"[OK] Wrote {len(clutch_treatments_df)} clutch↔treatment rows → {clutch_treatments_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build imaging treatment CSVs from imaging clutches draft + preview mapping sheets."
        )
    )
    parser.add_argument(
        "--clutches",
        type=pathlib.Path,
        default=pathlib.Path(
            "seed_kits/legacy_import/working/imaging_clutches_from_sheet_draft.csv"
        ),
        help="Path to imaging_clutches_from_sheet_draft.csv",
    )
    parser.add_argument(
        "--plasmid-preview",
        type=pathlib.Path,
        default=pathlib.Path(
            "seed_kits/legacy_import/raw/Unique_injected_plasmid__preview_dqm.xlsx"
        ),
        help="Path to Unique_injected_plasmid__preview_dqm.xlsx",
    )
    parser.add_argument(
        "--rna-preview",
        type=pathlib.Path,
        default=pathlib.Path(
            "seed_kits/legacy_import/raw/Unique_injected_rna__preview_dqm.xlsx"
        ),
        help="Path to Unique_injected_rna__preview_dqm.xlsx",
    )
    parser.add_argument(
        "--out-dir",
        type=pathlib.Path,
        default=pathlib.Path("seed_kits/legacy_import/working"),
        help="Directory to write treatment draft CSVs into",
    )
    args = parser.parse_args()
    build_treatments(
        args.clutches,
        args.plasmid_preview,
        args.rna_preview,
        args.out_dir,
    )


if __name__ == "__main__":
    main()
