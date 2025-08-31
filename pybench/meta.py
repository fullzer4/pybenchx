from __future__ import annotations

import platform
from typing import Optional, Tuple


def collect_git() -> Tuple[Optional[str], Optional[str], bool]:
    try:
        import subprocess

        def _run(cmd):
            return subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()

        branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or None
        sha = _run(["git", "rev-parse", "--short", "HEAD"]) or None
        dirty = bool(_run(["git", "status", "--porcelain"]))
        return branch, sha, dirty
    except Exception:
        return None, None, False


def tool_version() -> str:
    try:
        import importlib.metadata as im
        return im.version("pybenchx")
    except Exception:
        return "0.0.0"


def runtime_strings() -> tuple[str, str]:
    cpu = platform.processor() or platform.machine()
    runtime = f"python {platform.python_version()} ({platform.machine()}-{platform.system().lower()})"
    return cpu, runtime


def env_strings() -> tuple[str, str]:
    py_ver = platform.python_version()
    os_str = f"{platform.system()} {platform.release()} ({platform.machine()})"
    return py_ver, os_str


__all__ = ["collect_git", "tool_version", "runtime_strings", "env_strings"]
