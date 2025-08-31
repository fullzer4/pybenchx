from __future__ import annotations

import hashlib
import os


def _module_name_for_path(path: str) -> str:
    """Stable unique module name for importing standalone files."""
    p = os.path.abspath(path)
    h = hashlib.sha1(p.encode("utf-8")).hexdigest()[:12]
    stem = os.path.splitext(os.path.basename(p))[0]
    return f"pybenchx_{stem}_{h}"


__all__ = ["_module_name_for_path"]
