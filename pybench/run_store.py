# Placeholder I/O helpers for saving and loading Run JSON files under .pybenchx/
# Implementations to be added later.

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from .run_model import Run


def get_root(base: Optional[Path] = None) -> Path:
    base = base or Path.cwd()
    return (base / ".pybenchx").resolve()


def ensure_dirs(root: Path) -> None:
    for sub in (root / "runs", root / "baselines", root / "diffs", root / "suite", root / "machine"):
        sub.mkdir(parents=True, exist_ok=True)


def _ts_now() -> str:
    # 2025-08-30T2132Z
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%MZ")


def run_filename(meta: dict, label: Optional[str] = None) -> str:
    ts = meta.get("started_at") or _ts_now()
    branch = (meta.get("git") or {}).get("branch") or "detached"
    sha = (meta.get("git") or {}).get("sha") or "unknown"
    profile = meta.get("profile") or "smoke"
    parts = [ts, f"{branch}@{sha}", f"{profile}"]
    if label:
        parts.append(label)
    return ".".join(["_".join(parts[:-1]), parts[-1]]) + ".json" if label else f"{ts}_{branch}@{sha}.{profile}.json"


def save_run(run: Run, label: Optional[str] = None, *, root: Optional[Path] = None) -> Path:
    root = get_root(root)
    ensure_dirs(root)
    meta = asdict(run.meta)
    fname = run_filename(meta, label)
    path = root / "runs" / fname
    with path.open("w", encoding="utf-8") as f:
        json.dump(asdict(run), f, indent=2)
    return path


def save_baseline(run: Run, name: str, *, root: Optional[Path] = None) -> Path:
    root = get_root(root)
    ensure_dirs(root)
    path = root / "baselines" / f"{name}.json"
    from dataclasses import asdict as _asdict
    with path.open("w", encoding="utf-8") as f:
        json.dump(_asdict(run), f, indent=2)
    return path


def load_run(path: Path) -> Run:
    from .run_model import Run, RunMeta, VariantResult, StatSummary  # local import
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    meta = RunMeta(**data["meta"])  # type: ignore[arg-type]
    results = []
    for vr in data.get("results", []):
        stats = StatSummary(**vr["stats"])  # type: ignore[arg-type]
        results.append(VariantResult(**{**vr, "stats": stats}))  # type: ignore[arg-type]
    return Run(meta=meta, suite_signature=data.get("suite_signature", ""), results=results)


def load_baseline(name_or_path: str, *, root: Optional[Path] = None) -> Tuple[str, Run]:
    p = Path(name_or_path)
    if p.suffix == ".json" and p.exists():
        return (p.name, load_run(p))
    root = get_root(root)
    path = root / "baselines" / f"{name_or_path}.json"
    return (path.name, load_run(path))


__all__ = [
    "get_root",
    "ensure_dirs",
    "save_run",
    "save_baseline",
    "load_run",
    "load_baseline",
    "run_filename",
]
