from __future__ import annotations

import sys
import pathlib
import pandas as pd
from sqlalchemy import text

# repo bootstrap
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carp_app.ui.lib.app_ctx import get_engine  # type: ignore


FISH_XLSX = "seed_kits/2025-11-15-121231-autoload/fish.xlsx"


def main() -> None:
    eng = get_engine()

    df = pd.read_excel(FISH_XLSX)
    if "nickname" not in df.columns:
        raise RuntimeError(f"{FISH_XLSX} must have a 'nickname' column")

    # Normalize nicknames
    df["nickname_norm"] = df["nickname"].astype(str).str.strip()

    # Background-style rows we care about
    target_nicks = {"casper", "casper/rnf"}
    bg_rows = df[df["nickname_norm"].str.lower().isin(target_nicks)].copy()
    if bg_rows.empty:
        print("[INFO] No casper/casper-rnf rows found in fish.xlsx; nothing to seed.")
        return

    with eng.begin() as cx:
        # existing lines by nickname
        existing = pd.read_sql(
            text("SELECT nickname::text AS nickname FROM public.fish_lines"),
            cx,
        )
        existing_nicks = {str(r.nickname).strip() for _, r in existing.iterrows()}

        inserted = 0

        for _, r in bg_rows.iterrows():
            nick = str(r["nickname_norm"]).strip()
            if nick in existing_nicks:
                continue

            # try to use genetic_background / stage if present; otherwise defaults
            bg = str(r.get("genetic_background", "") or "").strip() or "casper"
            stage = str(r.get("line_building_stage", "") or "").strip() or "legacy"

            line_code = f"LINE-{nick.replace(' ', '').replace('/', '_')[:16]}"

            print(f"[SEED] inserting background line for nickname='{nick}' "
                  f"bg='{bg}' stage='{stage}' line_code='{line_code}'")

            cx.execute(
                text(
                    """
                    INSERT INTO public.fish_lines (
                      id,
                      line_code,
                      nickname,
                      genetic_background,
                      line_building_stage,
                      notes,
                      created_at,
                      fish_group_id,
                      group_instance_code
                    )
                    VALUES (
                      gen_random_uuid(),
                      :line_code,
                      :nickname,
                      :bg,
                      :stage,
                      'auto-seeded background line from fish.xlsx',
                      now(),
                      NULL,
                      NULL
                    )
                    """
                ),
                {
                    "line_code": line_code,
                    "nickname": nick,
                    "bg": bg,
                    "stage": stage,
                },
            )
            inserted += 1

    print(f"[OK] background lines seeded: {inserted}")


if __name__ == "__main__":
    main()
