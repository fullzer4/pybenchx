"""Generate stable suite signatures derived from case definitions."""

from __future__ import annotations

import hashlib
from typing import Iterable


def _case_fingerprint(c: object) -> str:
    """Return a normalized string fingerprint for a case-like object."""
    name = getattr(c, "name", "?")
    group = getattr(c, "group", None)
    params = getattr(c, "params", None)
    group_s = group if group is not None else "-"

    def norm_params(p):
        if not p:
            return ""
        items = []
        for k in sorted(p.keys()):
            vals = list(p[k])
            vals_s = ",".join(sorted(repr(v) for v in vals))
            items.append(f"{k}=[{vals_s}]")
        return ";".join(items)

    return f"{group_s}|{name}|{norm_params(params)}"


def suite_signature_from_cases(cases: Iterable[object]) -> str:
    """Compute a deterministic hash representing a set of cases."""
    h = hashlib.sha1()
    fps = sorted(_case_fingerprint(c) for c in cases)
    for fp in fps:
        h.update(fp.encode("utf-8"))
    return h.hexdigest()


__all__ = ["suite_signature_from_cases"]
