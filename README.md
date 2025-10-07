# PyBench — precise microbenchmarks for Python

[![CI](https://github.com/fullzer4/pybenchx/actions/workflows/ci.yml/badge.svg)](https://github.com/fullzer4/pybenchx/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pybenchx?label=PyPI)](https://pypi.org/project/pybenchx/)
[![Python Versions](https://img.shields.io/pypi/pyversions/pybenchx.svg)](https://pypi.org/project/pybenchx/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://static.pepy.tech/badge/pybenchx)](https://pepy.tech/project/pybenchx)
[![Ruff](https://img.shields.io/badge/lint-ruff-6E62E5.svg)](https://docs.astral.sh/ruff/)
[![Docs](https://img.shields.io/badge/docs-website-0A7EA4.svg)](https://fullzer4.github.io/pybenchx/)

Practical microbenchmarks for Python—tight iteration cycles, precise hot-path timing, and storage that makes comparisons and regression gates effortless.

Run benchmarks with one command:

```bash
pybench run examples/ [-k keyword] [-P key=value ...]
```

## ✨ Highlights

- Simple API: use the `@bench(...)` decorator or suites with `Bench` + `BenchContext.start()/end()` to isolate the hot path.
- Auto-discovery: `pybench run <dir>` expands to `**/*bench.py`.
- Powerful parameterization: generate Cartesian products with `params={...}` or define per-case `args/kwargs`.
- On-the-fly overrides: `-P key=value` adjusts `n`, `repeat`, `warmup`, `group`, or custom params without editing code.
- Solid timing model: monotonic clock, warmup, GC control, and context fast-paths.
- Smart calibration: per-variant iteration tuning to hit a target budget.
- Rich reports: aligned tables with percentiles, iter/s, min…max, baseline markers, and speedups vs. base.
- HTML charts: export benchmarks as self-contained Chart.js dashboards with `--export chart`.
- History tooling: runs auto-save to `.pybenchx/`; list, inspect stats, clean, or compare with `--vs {name,last}`.

## 🚀 Quickstart

### 📦 Install

- pip
  ```bash
  pip install pybenchx
  ```
- uv
  ```bash
  uv pip install pybenchx
  ```

### 🧪 Example benchmark

See `examples/strings_bench.py` for both styles:

```python
from pybench import bench, Bench, BenchContext

@bench(name="join", n=1000, repeat=10)
def join(sep: str = ","):
    sep.join(str(i) for i in range(100))

suite = Bench("strings")

@suite.bench(name="join-baseline", baseline=True)
def join_baseline(b: BenchContext):
    s = ",".join(str(i) for i in range(50))
    b.start(); _ = ",".join([s] * 5); b.end()
```

### 🏎️ Running

- Run all examples: `pybench run examples/`
- Filter variants: `pybench run examples/ -k join`
- Override params at runtime: `pybench run examples/ -P repeat=5 -P n=10000`

### 📚 Learn more

- [CLI reference](https://fullzer4.github.io/pybenchx/cli) — discovery rules, profiles, overrides, exports, comparisons.
- [Examples & cookbook](https://fullzer4.github.io/pybenchx/examples) — real-world patterns, CI recipes, history workflows.
- [Behavior & internals](https://fullzer4.github.io/pybenchx/behavior) — timing model, calibration, accuracy notes.
- [API reference](https://fullzer4.github.io/pybenchx/api) — decorators, suites, storage helpers, reporters.
