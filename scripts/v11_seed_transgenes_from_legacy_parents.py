#!/usr/bin/env python3
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


@dataclass
class TransgeneKey:
    base_code: str
    allele_nickname: str


def get_engine() -> Engine:
    url = os.environ.get("DB_URL")
    if not url:
        raise SystemExit("DB_URL must be set")
    print(f"DB_URL={url}")
    return create_engine(url)


def _norm_code(s: str | None) -> str:
    """
    Normalize legacy labels and basecodes so that all of these collide:

      'pDQM005', 'pdqm-5', 'PDQM005', 'pdqm_0005' → 'pdqm5'
      'MGCO35',  'mgco-35', 'mgco035'             → 'mgco35'
      'pSWIN01', 'pswin-1'                        → 'pswin1'

    We then use this normalized key to look up the exact base_code string
    stored in public.constructs.base_code.
    """
    if s is None:
        return ""
    t = str(s).strip().lower()
    t = t.replace(" ", "")

    m = re.match(r"^([a-z]+)[\-\_:]*(\d+)$", t)
    if m:
        prefix = m.group(1)
        num = int(m.group(2))
        return f"{prefix}{num}"

    return t.replace("-", "").replace("_", "")


def build_construct_basecode_map(engine: Engine) -> Dict[str, str]:
    """
    Map any construct_code/base_code variant → canonical base_code
    (exact string from constructs.base_code).
    """
    sql = text(
        """
        SELECT
          construct_code,
          base_code
        FROM public.constructs
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    for c in ["construct_code", "base_code"]:
        df[c] = df[c].astype("string").fillna("").str.strip()

    mapping: Dict[str, str] = {}
    for _, r in df.iterrows():
        base = r["base_code"]
        if not base:
            continue
        base_canon = base
        mapping[_norm_code(base)] = base_canon
        if r["construct_code"]:
            mapping[_norm_code(r["construct_code"])] = base_canon

    print(f"[constructs] canonical base_code map entries: {len(mapping)}")
    return mapping


def load_parent_defs(engine: Engine, basecode_map: Dict[str, str]) -> pd.DataFrame:
    """
    Legacy parent definitions → per-parent (base_code, allele_nickname) pairs.

    Rules:
      • Use plasmid_base_code as the *line* transgene anchor.
      • Treat plasmid_base_code and allele as comma-separated lists.
      • Normalize each basecode via basecode_map (constructs.base_code).
      • Zip basecodes and allele nicknames positionally:
            "pDQM005,pDQM104" + "301,324"
        → (pdqm-5, "301"), (pdqm-104, "324")
      • Skip injection-only mix plasmids (e.g. pdqm-104) when minting alleles.
    """
    sql = text(
        """
        SELECT
          parent_fish_name,
          plasmid_base_code,
          allele,
          injected_rna,
          injected_plasmid
        FROM raw.legacy_parent_definitions_v9
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    for c in ["parent_fish_name", "plasmid_base_code", "allele"]:
        df[c] = df[c].astype("string").fillna("").str.strip()

    rows: List[Dict[str, str]] = []
    missing_codes: set[str] = set()

    for _, r in df.iterrows():
        parent_name = (r["parent_fish_name"] or "").strip()
        base_raw = (r["plasmid_base_code"] or "").strip()
        allele_raw = (r["allele"] or "").strip()

        if not parent_name or not base_raw or not allele_raw:
            continue

        base_tokens = [b.strip() for b in base_raw.split(",") if b.strip()]
        allele_tokens = [a.strip() for a in allele_raw.split(",") if a.strip()]

        # Zip positionally; ignore any extra tokens on either side.
        for base_token, allele_nick in zip(base_tokens, allele_tokens):
            canon = basecode_map.get(_norm_code(base_token), "")
            if not canon:
                missing_codes.add(base_token)
                continue

            # Do NOT mint alleles for pdqm-104 (injection mix plasmid).
            if canon == "pdqm-104":
                continue

            rows.append(
                {
                    "parent_fish_name": parent_name,
                    "canonical_base_code": canon,
                    "allele_nickname": allele_nick,
                    "candidate_code": base_token,
                }
            )

    if missing_codes:
        print("[WARN] parent candidate_code with no construct match (skipped):")
        for v in sorted(missing_codes):
            print("  -", v)

    parent_defs = pd.DataFrame(rows)
    if parent_defs.empty:
        print("[parent_defs] rows with canonical base_code + allele_nickname: 0")
        return parent_defs

    # De-dup in case multiple rows describe the same (base_code, nickname)
    parent_defs = (
        parent_defs
        .drop_duplicates(
            subset=["canonical_base_code", "allele_nickname", "parent_fish_name"]
        )
        .reset_index(drop=True)
    )

    print(
        f"[parent_defs] rows with canonical base_code + allele_nickname: "
        f"{len(parent_defs)}"
    )
    return parent_defs


def load_clutch_parents(engine: Engine) -> pd.DataFrame:
    sql = text(
        """
        SELECT
          clutch_code,
          parent_female_label,
          parent_male_label,
          parent_female_allele,
          parent_male_allele
        FROM raw.legacy_clutch_parents_v9
        """
    )
    with engine.begin() as cx:
        df = pd.read_sql(sql, cx)

    for c in ["clutch_code", "parent_female_label", "parent_male_label"]:
        df[c] = df[c].astype("string").fillna("").str.strip()

    # parent_*_allele are legacy nicknames; we keep them as strings
    df["parent_female_allele_nickname"] = (
        df["parent_female_allele"].astype("string").fillna("").str.strip()
    )
    df["parent_male_allele_nickname"] = (
        df["parent_male_allele"].astype("string").fillna("").str.strip()
    )

    print(f"[clutch_parents] rows: {len(df)}")
    return df


def ensure_transgenes(engine: Engine, parent_defs: pd.DataFrame) -> int:
    base_codes = sorted(
        {bc for bc in parent_defs["canonical_base_code"].unique() if bc}
    )

    with engine.begin() as cx:
        cols = pd.read_sql(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'transgenes'
                """
            ),
            cx,
        )["column_name"].tolist()

        if "transgene_base_code" not in cols:
            raise SystemExit(
                "[ERROR] public.transgenes is missing transgene_base_code column"
            )

        existing = pd.read_sql(
            text("SELECT transgene_base_code FROM public.transgenes"), cx
        )
        existing_codes = set(existing["transgene_base_code"].tolist())

        inserted = 0
        for bc in base_codes:
            if bc in existing_codes:
                continue
            cx.execute(
                text(
                    """
                    INSERT INTO public.transgenes (transgene_base_code)
                    VALUES (:bc)
                    ON CONFLICT (transgene_base_code) DO NOTHING;
                    """
                ),
                {"bc": bc},
            )
            inserted += 1

    print(f"[transgenes] inserted {inserted} new row(s)")
    return inserted


def ensure_transgene_alleles(
    engine: Engine,
    parent_defs: pd.DataFrame,
) -> Dict[Tuple[str, str], int]:
    """
    For each (base_code, allele_nickname) pair, call public.ensure_transgene_allele
    and return a mapping:

      (base_code, allele_nickname) → allele_number
    """
    combos: Dict[Tuple[str, str], TransgeneKey] = {}
    for _, r in parent_defs.iterrows():
        bc = (r["canonical_base_code"] or "").strip()
        nick = (r["allele_nickname"] or "").strip()
        if not bc or not nick:
            continue
        k = TransgeneKey(base_code=bc, allele_nickname=nick)
        combos[(k.base_code, k.allele_nickname)] = k

    uniq_keys = sorted(combos.values(), key=lambda k: (k.base_code, k.allele_nickname))

    allele_map: Dict[Tuple[str, str], int] = {}
    created = 0
    reused = 0

    with engine.begin() as cx:
        for k in uniq_keys:
            res = cx.execute(
                text(
                    """
                    SELECT
                      transgene_base_code,
                      allele_number,
                      allele_name,
                      allele_nickname
                    FROM public.ensure_transgene_allele(:bc, :nick)
                    """
                ),
                {"bc": k.base_code, "nick": k.allele_nickname},
            )
            row = res.fetchone()
            if not row:
                print(
                    f"[WARN] ensure_transgene_allele returned no row for "
                    f"{k.base_code} / {k.allele_nickname}"
                )
                continue
            allele_number = int(row._mapping["allele_number"])
            key = (k.base_code, k.allele_nickname)
            if key in allele_map:
                reused += 1
            else:
                created += 1
            allele_map[key] = allele_number

    print(
        f"[ensure_transgene_alleles] allocator calls: {len(uniq_keys)}, "
        f"unique allele keys: {len(allele_map)}, "
        f"created (or first-seen): {created}, reused: {reused}"
    )
    return allele_map


def seed_clutch_transgene_links(
    engine: Engine,
    parent_defs: pd.DataFrame,
    clutch_parents: pd.DataFrame,
    allele_map: Dict[Tuple[str, str], int],
) -> int:
    """
    Build raw.legacy_clutch_transgene_alleles_v9 as a staging table linking:

      clutch_code → parent_role → (transgene_base_code, allele_number)

    Using canonical allele_number from ensure_transgene_allele.
    """
    # Map parent name → (base_code, allele_nickname)
    parent_map: Dict[str, Tuple[str, str]] = {}
    for _, r in parent_defs.iterrows():
        name = (r["parent_fish_name"] or "").strip()
        bc = (r["canonical_base_code"] or "").strip()
        nick = (r["allele_nickname"] or "").strip()
        if not name or not bc or not nick:
            continue
        parent_map[name] = (bc, nick)

    with engine.begin() as cx:
        df_cl = pd.read_sql(
            text("SELECT id::text AS clutch_id, clutch_code FROM public.clutches"),
            cx,
        )
    clutch_id_map = {
        (row["clutch_code"] or "").strip(): row["clutch_id"]
        for _, row in df_cl.iterrows()
    }

    rows: List[Dict[str, object]] = []

    for _, r in clutch_parents.iterrows():
        clutch_code = (r["clutch_code"] or "").strip()
        if not clutch_code:
            continue
        clutch_id = clutch_id_map.get(clutch_code)

        for role, label_col, nick_col in [
            ("mother", "parent_female_label", "parent_female_allele_nickname"),
            ("father", "parent_male_label", "parent_male_allele_nickname"),
        ]:
            label = (r[label_col] or "").strip()
            nick = (r[nick_col] or "").strip()
            if not label or not nick:
                continue

            if label not in parent_map:
                continue
            bc, parent_nick = parent_map[label]

            # Use the allocator result
            allele_key = (bc, parent_nick)
            allele_number = allele_map.get(allele_key)
            has_tga = allele_number is not None

            rows.append(
                {
                    "clutch_code": clutch_code,
                    "clutch_id": clutch_id,
                    "parent_role": role,
                    "parent_label": label,
                    "transgene_base_code": bc,
                    "allele_nickname": parent_nick,
                    "allele_number": allele_number,
                    "transgene_allele_id": None,
                    "has_transgene_allele": has_tga,
                }
            )

    df_out = pd.DataFrame(rows)
    print(f"[clutch_transgene_links] candidate rows: {len(df_out)}")

    with engine.begin() as cx:
        cx.execute(text("TRUNCATE raw.legacy_clutch_transgene_alleles_v9"))
        if not df_out.empty:
            df_out.to_sql(
                "legacy_clutch_transgene_alleles_v9",
                cx,
                schema="raw",
                if_exists="append",
                index=False,
            )

    print(
        "[clutch_transgene_links] wrote rows to raw.legacy_clutch_transgene_alleles_v9"
    )
    return len(df_out)


def main() -> None:
    eng = get_engine()

    basecode_map = build_construct_basecode_map(eng)
    parent_defs = load_parent_defs(eng, basecode_map)
    clutch_parents = load_clutch_parents(eng)

    ensure_transgenes(eng, parent_defs)
    allele_map = ensure_transgene_alleles(eng, parent_defs)
    n_links = seed_clutch_transgene_links(eng, parent_defs, clutch_parents, allele_map)

    print(
        f"[SUMMARY] transgenes + alleles seeded from legacy parents via allocator; "
        f"legacy clutch ⇄ transgene allele links staged: {n_links}"
    )


if __name__ == "__main__":
    main()
