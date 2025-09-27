import pandas as pd

from lib.db import fetch_df
from .utils import parse_date


def build_preview(engine, df_01, df_10, df_02, default_batch):
    if df_01 is None or df_01.empty:
        return pd.DataFrame()

    fish = df_01.copy()
    if "batch_label" not in fish.columns:
        fish["batch_label"] = None
    fish["batch_label"] = fish["batch_label"].apply(
        lambda v: default_batch if (v is None or str(v).strip() == "") else v
    )
    fish["date_of_birth"] = fish["date_of_birth"].apply(parse_date)

    base = fish.rename(columns={"name": "fish_name"})[
        [
            "fish_name",
            "nickname",
            "batch_label",
            "line_building_stage",
            "date_of_birth",
            "strain",
            "description",
        ]
    ].copy()

    tg_df = pd.DataFrame(columns=["fish_name", "transgenes"])
    alle_df = pd.DataFrame(columns=["fish_name", "alleles"])

    if df_10 is not None and not df_10.empty:
        links = df_10.copy()

        # Optional display names from df_02
        disp = None
        if df_02 is not None and not df_02.empty and "name" in df_02.columns:
            disp = df_02[["transgene_base_code", "name"]].copy()
            disp["disp_name"] = disp["name"].apply(
                lambda x: x.strip() if isinstance(x, str) and x.strip() else None
            )
            disp["disp_name"] = disp.apply(
                lambda r: r["disp_name"]
                if r["disp_name"]
                else r["transgene_base_code"],
                axis=1,
            )

        l2 = links.copy()
        for c in ["fish_name", "transgene_base_code", "allele_number", "zygosity"]:
            if c not in l2.columns:
                l2[c] = None

        if disp is not None:
            l2 = l2.merge(
                disp[["transgene_base_code", "disp_name"]],
                on="transgene_base_code",
                how="left",
            )
            l2["tg_name"] = l2.apply(
                lambda r: r["disp_name"]
                if isinstance(r.get("disp_name"), str) and r["disp_name"].strip()
                else r.get("transgene_base_code"),
                axis=1,
            )
        else:
            l2["tg_name"] = l2["transgene_base_code"]

        g_tg = (
            l2.dropna(subset=["fish_name"])
            .groupby("fish_name")["tg_name"]
            .apply(
                lambda s: ", ".join(
                    sorted({x for x in s if isinstance(x, str) and x.strip()})
                )
            )
        )
        tg_df = g_tg.reset_index().rename(columns={"tg_name": "transgenes"})

        def _alle_label(row):
            base = row.get("transgene_base_code")
            ann = row.get("allele_number")
            base = base if isinstance(base, str) and base.strip() else ""
            ann = ann if isinstance(ann, str) and ann.strip() else ""
            return f"{base}({ann})" if (base and ann) else (base or "")

        l2["alle_label"] = l2.apply(_alle_label, axis=1)
        g_alle = (
            l2.dropna(subset=["fish_name"])
            .groupby("fish_name")["alle_label"]
            .apply(
                lambda s: ", ".join(
                    sorted({x for x in s if isinstance(x, str) and x.strip()})
                )
            )
        )
        alle_df = g_alle.reset_index().rename(columns={"alle_label": "alleles"})

    prev = base.merge(tg_df, on="fish_name", how="left").merge(
        alle_df, on="fish_name", how="left"
    )
    prev["transgenes"] = prev["transgenes"].fillna("")
    prev["alleles"] = prev["alleles"].fillna("")
    prev["auto_fish_code"] = "(to be generated)"
    prev["tank"] = ""

    cols = [
        "fish_name",
        "nickname",
        "auto_fish_code",
        "batch_label",
        "line_building_stage",
        "date_of_birth",
        "tank",
        "transgenes",
        "alleles",
        "description",
    ]
    prev = prev[cols]

    with engine.connect() as cx:
        existing = fetch_df(cx, "select name from public.fish")
    existing_names = set(existing["name"].tolist()) if not existing.empty else set()
    prev["status"] = prev["fish_name"].apply(
        lambda n: "exists" if n in existing_names else "new"
    )

    return prev