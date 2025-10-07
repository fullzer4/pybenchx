"""Minimal ANSI helper utilities for table rendering."""

from __future__ import annotations

import re

RESET = "\x1b[0m"
YELLOW = "\x1b[33;1m"
CYAN = "\x1b[36;1m"
MAGENTA = "\x1b[35;1m"
DIM = "\x1b[2m"
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(s: str) -> str:
    """Remove ANSI escape sequences from ``s``."""
    return _ANSI_RE.sub("", s)


def visible_len(s: str) -> int:
    """Return display length of a string with ANSI codes."""
    return len(strip_ansi(s))


def pad_cell(cell: str, width: int, align: str) -> str:
    """Pad ``cell`` to ``width`` respecting ANSI codes and alignment."""
    length = visible_len(cell)
    if length >= width:
        return cell
    pad = " " * (width - length)
    return (pad + cell) if align != "<" else (cell + pad)


__all__ = [
    "RESET",
    "YELLOW",
    "CYAN",
    "MAGENTA",
    "DIM",
    "strip_ansi",
    "visible_len",
    "pad_cell",
]
