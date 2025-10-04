# Storage management for benchmark runs and baselines.
# Handles saving, loading, and auto-tracking of runs.

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, List

from .run_model import Run


def get_root(base: Optional[Path] = None) -> Path:
    """Get .pybenchx root directory."""
    base = base or Path.cwd()
    return (base / ".pybenchx").resolve()


def ensure_dirs(root: Path) -> None:
    """Create standard directory structure."""
    for sub in (root / "runs", root / "baselines", root / "diffs", root / "suite", root / "machine"):
        sub.mkdir(parents=True, exist_ok=True)


def _ts_now() -> str:
    """Generate timestamp in format: 2025-08-30T2132Z"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%MZ")


def run_filename(meta: dict, label: Optional[str] = None) -> str:
    """Generate filename for a run."""
    ts = meta.get("started_at") or _ts_now()
    branch = (meta.get("git") or {}).get("branch") or "detached"
    sha = (meta.get("git") or {}).get("sha") or "unknown"
    profile = meta.get("profile") or "quick"
    parts = [ts, f"{branch}@{sha}", f"{profile}"]
    if label:
        parts.append(label)
    return ".".join(["_".join(parts[:-1]), parts[-1]]) + ".json" if label else f"{ts}_{branch}@{sha}.{profile}.json"


def auto_save_run(run: Run, *, root: Optional[Path] = None) -> Path:
    """Auto-save every run to .pybenchx/runs/ (for history tracking).
    
    This enables:
    - Always having a baseline to compare against
    - Historical performance tracking
    - Easy rollback to previous runs
    """
    return save_run(run, label=None, root=root)


def save_run(run: Run, label: Optional[str] = None, *, root: Optional[Path] = None) -> Path:
    """Save a run with optional label."""
    root = get_root(root)
    ensure_dirs(root)
    meta = asdict(run.meta)
    fname = run_filename(meta, label)
    path = root / "runs" / fname
    with path.open("w", encoding="utf-8") as f:
        json.dump(asdict(run), f, indent=2)
    return path


def save_baseline(run: Run, name: str, *, root: Optional[Path] = None) -> Path:
    """Save a named baseline."""
    root = get_root(root)
    ensure_dirs(root)
    path = root / "baselines" / f"{name}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(asdict(run), f, indent=2)
    return path


def load_run(path: Path) -> Run:
    """Load a run from JSON file."""
    from .run_model import Run, RunMeta, VariantResult, StatSummary  # local import
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    meta = RunMeta(**data["meta"])  # type: ignore[arg-type]
    results = []
    for vr in data.get("results", []):
        stats = StatSummary(**vr["stats"])  # type: ignore[arg-type]
        results.append(VariantResult(**{**vr, "stats": stats}))  # type: ignore[arg-type]
    return Run(meta=meta, suite_signature=data.get("suite_signature", ""), results=results)


def load_baseline(name_or_path: str, *, root: Optional[Path] = None) -> Tuple[str, Run]:
    """Load a baseline by name or path.
    
    Usage:
        load_baseline("main")           # from .pybenchx/baselines/main.json
        load_baseline("path/to/run.json")  # absolute path
    """
    p = Path(name_or_path)
    if p.suffix == ".json" and p.exists():
        return (p.name, load_run(p))
    root = get_root(root)
    path = root / "baselines" / f"{name_or_path}.json"
    return (path.name, load_run(path))


def get_latest_run(*, root: Optional[Path] = None) -> Optional[Run]:
    """Get the most recent run from .pybenchx/runs/."""
    root = get_root(root)
    runs_dir = root / "runs"
    if not runs_dir.exists():
        return None
    
    run_files = sorted(runs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not run_files:
        return None
    
    return load_run(run_files[0])


def list_baselines(*, root: Optional[Path] = None) -> List[str]:
    """List all available baseline names."""
    root = get_root(root)
    baselines_dir = root / "baselines"
    if not baselines_dir.exists():
        return []
    
    return sorted([p.stem for p in baselines_dir.glob("*.json")])


def list_recent_runs(limit: int = 10, *, root: Optional[Path] = None) -> List[Path]:
    """List recent runs (most recent first)."""
    root = get_root(root)
    runs_dir = root / "runs"
    if not runs_dir.exists():
        return []
    
    run_files = sorted(runs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return run_files[:limit]


__all__ = [
    "get_root",
    "ensure_dirs",
    "save_run",
    "auto_save_run",
    "save_baseline",
    "load_run",
    "load_baseline",
    "get_latest_run",
    "list_baselines",
    "list_recent_runs",
    "run_filename",
]

