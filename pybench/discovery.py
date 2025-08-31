from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import List, Sequence

from .path_utils import _module_name_for_path

GLOB = "**/*bench.py"


def discover(paths: Sequence[str]) -> List[Path]:
    files: List[Path] = []
    for p in paths:
        path = Path(p)
        if path.is_file():
            files.append(path.resolve())
        elif path.is_dir():
            base = path.resolve()
            files.extend(sorted(base.glob(GLOB)))
    return files


def load_module_from_path(path: Path) -> None:
    path = path.resolve()
    modname = _module_name_for_path(str(path))
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(modname, str(path))
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules[modname] = module
        # type: ignore[arg-type]
        spec.loader.exec_module(module)  # noqa: E501


__all__ = ["discover", "load_module_from_path", "GLOB"]
