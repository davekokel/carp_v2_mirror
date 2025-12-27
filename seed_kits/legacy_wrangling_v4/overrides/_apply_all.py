from __future__ import annotations

import pandas as pd

from seed_kits.legacy_wrangling_v4.overrides import (
    _apply_all as _self,  # noqa: F401
)
from seed_kits.legacy_wrangling_v4.overrides import (
    _apply_all,  # noqa: F401
)

from seed_kits.legacy_wrangling_v4.overrides import (
    _apply_all as __,  # noqa: F401
)

from seed_kits.legacy_wrangling_v4.overrides import (
    _apply_all as ___,  # noqa: F401
)

from seed_kits.legacy_wrangling_v4.overrides import 10_slug_marker_rules_v4  # type: ignore

def apply(df: pd.DataFrame) -> pd.DataFrame:
    df = 10_slug_marker_rules_v4.apply(df)
    return df
