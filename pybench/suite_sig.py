# Suite signature computation based on case definitions.
# Produces a stable hash from (case.name, group, params schema).

from __future__ import annotations

import hashlib
from typing import Iterable


def _case_fingerprint(c: object) -> str:
    # Lazy attribute access to avoid importing core here.
    name = getattr(c, "name", "?")
    group = getattr(c, "group", None)
    params = getattr(c, "params", None)
    group_s = group if group is not None else "-"

    def norm_params(p):
        if not p:
            return ""
        items = []
        for k in sorted(p.keys()):  # type: ignore[attr-defined]
            vals = list(p[k])  # type: ignore[index]
            vals_s = ",".join(sorted(repr(v) for v in vals))
            items.append(f"{k}=[{vals_s}]")
        return ";".join(items)

    return f"{group_s}|{name}|{norm_params(params)}"


def suite_signature_from_cases(cases: Iterable[object]) -> str:
    h = hashlib.sha1()
    fps = sorted(_case_fingerprint(c) for c in cases)
    for fp in fps:
        h.update(fp.encode("utf-8"))
    return h.hexdigest()


__all__ = ["suite_signature_from_cases"]
