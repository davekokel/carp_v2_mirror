from __future__ import annotations

from typing import Optional


def normalize_construct_code(raw: str | None) -> Optional[str]:
    """
    Canonical form: lowercase letters + '-' + non-zero-padded integer.

    Examples:
      'pDQM005'    -> 'pdqm-5'
      'pDQM-005'   -> 'pdqm-5'
      'PDQM5x'     -> 'pdqm-5'
      'mgco-35'    -> 'mgco-35'
      'MGCO035xyz' -> 'mgco-35'

    If we cannot find a letter-prefix + digit-sequence, return None.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None

    # 1) leading letters
    prefix_chars: list[str] = []
    i = 0
    while i < len(s) and s[i].isalpha():
        prefix_chars.append(s[i])
        i += 1

    if not prefix_chars:
        return None
    prefix = "".join(prefix_chars).lower()

    # 2) first integer run after the prefix (skip punctuation until digits)
    while i < len(s) and not s[i].isdigit():
        i += 1

    if i >= len(s) or not s[i].isdigit():
        return None

    digits: list[str] = []
    while i < len(s) and s[i].isdigit():
        digits.append(s[i])
        i += 1

    if not digits:
        return None

    n = int("".join(digits))  # strips zero-padding
    return f"{prefix}-{n}"
