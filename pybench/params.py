from __future__ import annotations

import itertools
from typing import Any, Dict, Iterable, List, Tuple

from .bench_model import Case


def fmt_value(v: Any) -> str:
    return repr(v) if isinstance(v, str) else str(v)


def make_variants(case: Case) -> List[Tuple[str, tuple, Dict[str, Any]]]:
    base_args = case.args
    base_kwargs = dict(case.kwargs)
    if not case.params:
        return [(case.name, base_args, base_kwargs)]

    keys = sorted(case.params.keys())
    value_lists = [list(case.params[k]) for k in keys]
    variants: List[Tuple[str, tuple, Dict[str, Any]]] = []
    for values in itertools.product(*value_lists):
        kw = dict(base_kwargs)
        for k, v in zip(keys, values):
            kw[k] = v
        label = ",".join(f"{k}={fmt_value(v)}" for k, v in zip(keys, values))
        vname = f"{case.name}[{label}]"
        variants.append((vname, base_args, kw))
    return variants


__all__ = ["make_variants", "fmt_value"]
