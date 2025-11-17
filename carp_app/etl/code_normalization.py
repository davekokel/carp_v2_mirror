from __future__ import annotations

import re
from typing import Optional

NA_VALUES = {"", "nan", "NaN", "NA", "N/A", None}


def normalize_base_code(raw: Optional[str]) -> str:
    """
    Normalize plasmid/transgene base codes so that variants like:
      pDQM005, PDQM-005, PDQM5  -> PDQM-5
      MGCO01, MGCO-001         -> MGCO-1

    Anything that is not 'letters + optional hyphen + digits'
    just gets uppercased and returned as-is.

    This MUST match how transgene_base_code is stored in v7:
      - 'PDQM-5', 'PDQM-34', 'MGCO-35', etc.
    """
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s or s.lower() in NA_VALUES:
        return ""

    s = s.upper().strip()

    # PREFIX[-_]0*DIGITS  -> PREFIX-int(DIGITS)
    m = re.match(r"^([A-Z]+)[-_]?0*([0-9]+)$", s)
    if m:
        prefix, num = m.groups()
        return f"{prefix}-{int(num)}"

    # Everything else: uppercased literal (e.g. SWINBURNE)
    return s
