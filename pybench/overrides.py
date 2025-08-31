from __future__ import annotations

from typing import Any, Dict

from .bench_model import Case


def _parse_value(v: str) -> Any:
    s = v.strip()
    if s.lower() in {"true", "false"}:
        return s.lower() == "true"
    if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
        try:
            return int(s)
        except Exception:
            pass
    try:
        return float(s)
    except Exception:
        pass
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        return s[1:-1]
    return s


def parse_overrides(pairs: list[str]) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}
    for p in pairs:
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        overrides[k.strip()] = _parse_value(v)
    return overrides


def apply_overrides(case: Case, overrides: Dict[str, Any]) -> Case:
    if not overrides:
        return case
    c = Case(
        name=case.name,
        func=case.func,
        mode=case.mode,
        group=case.group,
        n=case.n,
        repeat=case.repeat,
        warmup=case.warmup,
        args=tuple(case.args),
        kwargs=dict(case.kwargs),
        params=dict(case.params) if case.params else None,
        baseline=case.baseline,
    )
    for k, v in overrides.items():
        if k in {"n", "repeat", "warmup"}:
            setattr(c, k, int(v))
        elif k == "group":
            c.group = str(v)
        elif k == "baseline":
            if isinstance(v, bool):
                c.baseline = v
            else:
                c.baseline = str(v).lower() in {"1", "true", "yes", "on"}
        else:
            if c.params and k in c.params:
                c.params[k] = [v]
            else:
                c.kwargs[k] = v
    return c


__all__ = ["parse_overrides", "apply_overrides"]
