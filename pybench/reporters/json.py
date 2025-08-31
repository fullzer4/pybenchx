# Placeholder JSON reporter. Will format a Run as JSON or write to path.

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from ..run_model import Run


def render(run: Run) -> str:
    return json.dumps(asdict(run), indent=2)


def write(run: Run, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(run), encoding="utf-8")


__all__ = ["render", "write"]
