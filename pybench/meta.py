"""Collect metadata about the repository, environment, and tool version."""

from __future__ import annotations

import platform


def collect_git() -> tuple[str | None, str | None, bool]:
    """Return ``(branch, sha, dirty)`` for the current git checkout."""
    try:
        import subprocess

        def _run(cmd):
            output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
            return output.decode().strip()

        branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or None
        sha = _run(["git", "rev-parse", "--short", "HEAD"]) or None
        dirty = bool(_run(["git", "status", "--porcelain"]))
        return branch, sha, dirty
    except Exception:
        return None, None, False


def tool_version() -> str:
    """Return the installed ``pybenchx`` version or ``0.0.0`` when missing."""
    try:
        import importlib.metadata as im
        return im.version("pybenchx")
    except Exception:
        return "0.0.0"


def runtime_strings() -> tuple[str, str]:
    """Describe the current CPU and Python runtime string."""
    cpu = platform.processor() or platform.machine()
    runtime = (
        f"python {platform.python_version()} "
        f"({platform.machine()}-{platform.system().lower()})"
    )
    return cpu, runtime


def env_strings() -> tuple[str, str]:
    """Describe the Python version and operating system string."""
    py_ver = platform.python_version()
    os_str = f"{platform.system()} {platform.release()} ({platform.machine()})"
    return py_ver, os_str


__all__ = ["collect_git", "tool_version", "runtime_strings", "env_strings"]
