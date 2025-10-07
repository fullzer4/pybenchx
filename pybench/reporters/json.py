"""Utility functions for serializing runs to JSON."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from ..run_model import Run


def render(run: Run) -> str:
    """Return a formatted JSON string for ``run``."""
    return json.dumps(asdict(run), indent=2)


def write(run: Run, path: Path) -> None:
    """Write ``run`` to ``path`` ensuring parent directories exist."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(run), encoding="utf-8")


__all__ = ["render", "write"]
