# Changelog

## v1.2.0 — architecture refresh & richer docs

### Summary
This release tightens the ergonomics for day-to-day benchmarking, adds richer run management, and ships a complete documentation overhaul (README, guides, internals, and API reference).

### Highlights
- CLI quality-of-life:
  - `pybench run --vs {main,last}` for quick comparisons against saved history.
  - Storage helpers exposed directly (`pybench list`, `stats`, and `clean --keep N`).
  - Chart export (`--export chart[:PATH]`) now ships an interactive HTML (Chart.js) bundle.
- Run store upgrades:
  - `.pybenchx/` auto-initializes with a human-readable README and structured exports per format.
  - `run_store` exposes helpers for pruning history, resolving baselines, and computing storage stats.
- Reporter polish: table, Markdown, CSV, JSON, and chart outputs now share the same speedup/baseline logic, with consistent “≈ same” heuristics.

### Documentation & examples
- README rewritten to position pybenchx, highlight scope/non-goals, and walk through storage management.
- Docs refresh:
  - Overview, Getting Started, CLI, Behavior, Internals, and Examples expanded with workflows, `.pybenchx` explainer, and CI recipes.
  - New API reference hub with focused pages for decorators/suites, BenchContext & runner, run storage/comparison, and reporters.
- Examples now cover daily CLI workflows, budget tuning, history management, and automation patterns.

### Developer experience
- `CONTRIBUTING.md` expanded with branch workflow, lint/test commands, docs preview steps, release checklist, and quality gates.
- Project tooling documented: `ruff`, `pytest`, Astro docs site (`npm run dev` / `npm run lint`), and nightly regression tips.
- Release automation clarified: tags (`v*`) trigger CI publish via `hatch-vcs` versioning.

---

## v1.1.3 — new outputs, and modular refactor

### Summary
This release delivers new output capabilities (export and compare), and a refactor that reduces duplication (DRY) and improves maintainability.

### Highlights
- New run management: save runs, define baselines, compare, and export reports.
- Report parity: Markdown now mirrors the CLI table (baseline ★, “≈ same”, vs base).
- DRY: shared utilities for time formatting, percentiles, and speedups.
- Default profile is `smoke` (no calibration); “fast” was removed.

---

### Python 3.7+ compatibility (improvements and caveats)
- Fallback to `perf_counter() * 1e9` when `perf_counter_ns` is not available.
- Fallback for `statistics.fmean` (use sum/n) on versions lacking `fmean` (3.7).
- Fallback for `importlib.metadata.version` (falls back to `0.0.0` when unavailable).
- BenchContext reimplemented as a simple class with explicit `__slots__` — 3.7-friendly.

Known caveats on 3.7:
- Clock precision can vary by OS, slightly affecting percentiles/p-values.
- Without dataclass `slots=True`, memory overhead is marginally higher.
- In environments without Git, branch/sha metadata may be empty (handled gracefully).

---

### New output features and run management
- Report export via CLI:
  - `--export json|md|csv[:PATH]` (to stdout or a file).
  - Markdown includes: group, baseline ★, mean, p99, and “vs base” (shows “≈ same” when ≤1%).
- Saving and baselines:
  - `--save LABEL` stores the run under `.pybenchx/runs/`.
  - `--save-baseline NAME` stores it under `.pybenchx/baselines/`.
- Run comparison:
  - `--compare BASE|PATH` compares current run with a baseline; p-values via Mann–Whitney U (approx).
  - Failure policies via `--fail-on mean:%[,p99:%]`; `p99` uses the actual P99 delta.

Quick examples:
```bash
pybench examples/ --save latest
pybench examples/ --save-baseline main
pybench examples/ --export md:bench.md
pybench examples/ --compare main --fail-on mean:7%,p99:12%
```

---

### UX and execution
- `-k` filtering happens before warmup/measurement (avoids unnecessary work).
- CLI header shows `profile` and calibration budget.
- Stable suite signature (case hash) highlights changes between runs.

---

### Refactor and DRY (no breaking changes for end users)
- Core modularization: `bench_model`, `runner`, `timing`, `params`, `overrides`, `discovery`, `suite_sig`.
- New modules: `run_model`, `run_store`, `compare`, `meta`, `reporters/*`.
- Shared utilities in `pybench.utils`:
  - `fmt_time_ns`, `percentile`, `compute_speedups`.
- Reporters (table/markdown) now use the shared utilities.

---

### Behavior changes
- Removed `--profile fast`; `smoke` is the default; `thorough` remains ~1s with `repeat=30`.
- Unified “vs base” between table and markdown; shows “≈ same” at ≤1% difference.
- `p99` failure policy now uses the actual P99 delta (previously could proxy mean in some paths).

---

### Notes for contributors
- Cleaner, non-duplicated code: helpers centralized in `utils`.
- Reporters and comparators share the same baseline/speedups logic.
- Documentation updated (CLI, Getting Started, Examples, Internals) to match behavior.
