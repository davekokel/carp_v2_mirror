from __future__ import annotations

from pathlib import Path

import pandas as pd

from carp_app.ui.lib.page_engine import engine
from carp_app.ui.lib.csv_loaders_fluors import load_fluors_from_df
from carp_app.ui.lib.csv_loaders_tags import load_tags_from_df
from carp_app.ui.lib.csv_loaders_aliases import load_aliases_from_df
from carp_app.ui.lib.csv_loaders_dyes import load_dyes_from_df
from carp_app.ui.lib.csv_loaders_rnas import load_rnas_from_df
from carp_app.ui.lib.csv_loaders_plasmids import load_plasmids_from_df
from carp_app.ui.lib.csv_loaders_rna_fusions import load_rna_fusions_from_df
from carp_app.ui.lib.csv_loaders_plasmid_fusions import load_plasmid_fusions_from_df
from carp_app.ui.lib.csv_loaders_fish import load_fish_from_df


def autoload_seed_kit(seed_dir: Path, dry_run: bool = False) -> None:
    """
    Autoload a seed kit into the current DB, in dependency order.

    Loads (strict headers):
      1) fluors.csv
      2) tags.xlsx
      3) alias.csv
      4) dyes.csv
      5) rnas.csv
      6) plasmids.csv
      7) rna_fusions.csv      (validation only)
      8) plasmid_fusions.csv  (validation only)
      9) fish.xlsx
    """
    seed_dir = seed_dir.expanduser().resolve()
    if not seed_dir.exists():
        raise FileNotFoundError(seed_dir)

    print(f"[seed_autoload] Using seed kit: {seed_dir}")

    # 1) Fluors
    fluors_path = seed_dir / "fluors.csv"
    if fluors_path.exists():
        df = pd.read_csv(fluors_path, dtype=object)
        if dry_run:
            print(f"[dry-run] Would load {len(df)} fluors from {fluors_path}")
        else:
            print(f"[seed_autoload] Loading {len(df)} fluors from {fluors_path}")
            with engine().begin() as cx:
                created, updated, rows, soft_warn = load_fluors_from_df(df, cx)
            print(f"[seed_autoload] Fluors created: {created}, updated: {updated}")
            for w in soft_warn:
                print(f"[seed_autoload][fluors] WARNING: {w}")
    else:
        print(f"[seed_autoload] No fluors.csv in {seed_dir}, skipping.")

    # 2) Tags
    tags_path = seed_dir / "tags.xlsx"
    if tags_path.exists():
        df_tags = pd.read_excel(tags_path, dtype=object)
        if dry_run:
            print(f"[dry-run] Would load {len(df_tags)} tags from {tags_path}")
        else:
            print(f"[seed_autoload] Loading {len(df_tags)} tags from {tags_path}")
            with engine().begin() as cx:
                created, updated, df_norm = load_tags_from_df(df_tags, cx)
            print(f"[seed_autoload] Tags created: {created}, updated: {updated}")
    else:
        print(f"[seed_autoload] No tags.xlsx in {seed_dir}, skipping.")

    # 3) Aliases
    alias_path = seed_dir / "alias.csv"
    if alias_path.exists():
        df_alias = pd.read_csv(alias_path, dtype=object)
        if dry_run:
            print(f"[dry-run] Would load {len(df_alias)} aliases from {alias_path}")
        else:
            print(f"[seed_autoload] Loading {len(df_alias)} aliases from {alias_path}")
            with engine().begin() as cx:
                inserted, warnings = load_aliases_from_df(df_alias, cx)
            print(f"[seed_autoload] Aliases inserted: {inserted}")
            for w in warnings:
                print(f"[seed_autoload][aliases] WARNING: {w}")
    else:
        print(f"[seed_autoload] No alias.csv in {seed_dir}, skipping.")

    # 4) Dyes
    dyes_path = seed_dir / "dyes.csv"
    if dyes_path.exists():
        df_dyes = pd.read_csv(dyes_path, dtype=object)
        if dry_run:
            print(f"[dry-run] Would load {len(df_dyes)} dyes from {dyes_path}")
        else:
            print(f"[seed_autoload] Loading {len(df_dyes)} dyes from {dyes_path}")
            with engine().begin() as cx:
                created, updated, df_norm = load_dyes_from_df(df_dyes, cx)
            print(f"[seed_autoload] Dyes created: {created}, updated: {updated}")
    else:
        print(f"[seed_autoload] No dyes.csv in {seed_dir}, skipping.")

    # 5) RNAs
    rnas_path = seed_dir / "rnas.csv"
    if rnas_path.exists():
        df_rnas = pd.read_csv(rnas_path, dtype=object)
        if dry_run:
            print(f"[dry-run] Would load {len(df_rnas)} RNAs from {rnas_path}")
        else:
            print(f"[seed_autoload] Loading {len(df_rnas)} RNAs from {rnas_path}")
            with engine().begin() as cx:
                created, updated, df_norm = load_rnas_from_df(df_rnas, cx)
            print(f"[seed_autoload] RNAs created: {created}, updated: {updated}")
    else:
        print(f"[seed_autoload] No rnas.csv in {seed_dir}, skipping.")

    # 6) Plasmids
    plasmids_path = seed_dir / "plasmids.csv"
    if plasmids_path.exists():
        df_plasmids = pd.read_csv(plasmids_path, dtype=object)
        if dry_run:
            print(f"[dry-run] Would load {len(df_plasmids)} plasmids from {plasmids_path}")
        else:
            print(f"[seed_autoload] Loading {len(df_plasmids)} plasmids from {plasmids_path}")
            with engine().begin() as cx:
                created, updated, df_norm = load_plasmids_from_df(df_plasmids, cx)
            print(f"[seed_autoload] Plasmids created: {created}, updated: {updated}")
    else:
        print(f"[seed_autoload] No plasmids.csv in {seed_dir}, skipping.")

    # 7) RNA fusions (validation only)
    rf_path = seed_dir / "rna_fusions.csv"
    if rf_path.exists():
        df_rf = pd.read_csv(rf_path, dtype=object)
        if dry_run:
            print(f"[dry-run] Would validate {len(df_rf)} rna_fusions from {rf_path}")
        else:
            print(f"[seed_autoload] Validating {len(df_rf)} rna_fusions from {rf_path}")
            with engine().begin() as cx:
                valid_rf, warnings_rf = load_rna_fusions_from_df(df_rf, cx)
            print(f"[seed_autoload] RNA fusions valid rows: {valid_rf}")
            for w in warnings_rf:
                print(f"[seed_autoload][rna_fusions] WARNING: {w}")
    else:
        print(f"[seed_autoload] No rna_fusions.csv in {seed_dir}, skipping.")

    # 8) Plasmid fusions (validation only)
    pf_path = seed_dir / "plasmid_fusions.csv"
    if pf_path.exists():
        df_pf = pd.read_csv(pf_path, dtype=object)
        if dry_run:
            print(f"[dry-run] Would validate {len(df_pf)} plasmid_fusions from {pf_path}")
        else:
            print(f"[seed_autoload] Validating {len(df_pf)} plasmid_fusions from {pf_path}")
            with engine().begin() as cx:
                valid_pf, warnings_pf = load_plasmid_fusions_from_df(df_pf, cx)
            print(f"[seed_autoload] Plasmid fusions valid rows: {valid_pf}")
            for w in warnings_pf:
                print(f"[seed_autoload][plasmid_fusions] WARNING: {w}")
    else:
        print(f"[seed_autoload] No plasmid_fusions.csv in {seed_dir}, skipping.")

    # 9) Fish (seed last; depends on base tables)
    fish_path = seed_dir / "fish.xlsx"
    if fish_path.exists():
        df_fish = pd.read_excel(fish_path, dtype=object)
        if dry_run:
            print(f"[dry-run] Would load {len(df_fish)} fish from {fish_path}")
        else:
            print(f"[seed_autoload] Loading {len(df_fish)} fish from {fish_path}")
            with engine().begin() as cx:
                summary = load_fish_from_df(
                    df_fish,
                    cx,
                    seed_batch_id=fish_path.stem,
                    actor_email="seed_autoload",
                )
            print(
                f"[seed_autoload] Fish upserts: {summary['fish_upserts']}, "
                f"allele_links: {summary['allele_links']}, "
                f"tanks_ensured: {summary['tanks_ensured']}"
            )
            for w in summary.get("warnings", []):
                print(f"[seed_autoload][fish] WARNING: {w}")
    else:
        print(f"[seed_autoload] No fish.xlsx in {seed_dir}, skipping.")
