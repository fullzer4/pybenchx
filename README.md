# PyBench — precise microbenchmarks for Python

[![CI](https://github.com/fullzer4/pybenchx/actions/workflows/ci.yml/badge.svg)](https://github.com/fullzer4/pybenchx/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pybenchx?label=PyPI)](https://pypi.org/project/pybenchx/)
[![Python Versions](https://img.shields.io/pypi/pyversions/pybenchx.svg)](https://pypi.org/project/pybenchx/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://static.pepy.tech/badge/pybenchx)](https://pepy.tech/project/pybenchx)

Measure small, focused snippets with minimal boilerplate, auto-discovery, smart calibration, and a clean CLI (`pybench`).

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

- Run all examples
  ```bash
  pybench run examples/
  ```
- Filter by name
  ```bash
  pybench run examples/ -k join
  ```
- Override params at runtime
  ```bash
  pybench run examples/ -P repeat=5 -P n=10000
  ```

### 🎛️ Key CLI options

- Disable color
  ```bash
  pybench run examples/ --no-color
  ```
- Sorting
  ```bash
  pybench run examples/ --sort time --desc
  ```
- Time budget per variant (calibration)
  ```bash
  pybench run examples/ --budget 300ms     # total per variant; split across repeats
  pybench run examples/ --max-n 1000000    # cap calibrated n
  ```
- Profiles
  ```bash
  pybench run examples/ --profile thorough  # ~1s budget, repeat=30
  pybench run examples/ --profile smoke     # no calibration, repeat=3 (default)
  ```
- Save / Compare / Export
  ```bash
  pybench run examples/ --save latest
  pybench run examples/ --save-baseline main
  pybench run examples/ --compare main --fail-on mean:7%,p99:12%
  pybench run examples/ --export chart        # HTML dashboard (Chart.js)
  pybench run examples/ --export json         # JSON next to auto-saved run
  ```

### 🗂️ Manage history & baselines

- List everything under `.pybenchx/`
  ```bash
  pybench list
  pybench list --baselines
  ```
- Storage stats & cleanup
  ```bash
  pybench stats
  pybench clean --keep 50
  ```
- Compare quickly
  ```bash
  pybench run examples/ --vs main        # named baseline
  pybench run examples/ --vs last        # last auto-saved run
  ```

### 📊 Output

Header includes CPU, Python, perf_counter clock info, total time, and profile. Table shows speed vs baseline with percent:

```
(pybench) $ pybench run examples/
cpu: x86_64
runtime: python 3.13.5 (x86_64-linux) | perf_counter: res=1.0e-09s, mono=True
time: 23.378s | profile: smoke, budget=-, max-n=1000000, sequential
benchmark                          time (avg)       iter/s              (min … max)          p75          p99         p995      vs base
join                                 13.06 µs       76.6 K      13.00 µs … 13.21 µs     13.08 µs     13.20 µs     13.21 µs            -
join_param[n=100,sep='-']            13.17 µs       75.9 K      12.79 µs … 13.72 µs     13.37 µs     13.70 µs     13.71 µs            -
join_param[n=100,sep=':']            13.06 µs       76.6 K      12.85 µs … 13.23 µs     13.14 µs     13.23 µs     13.23 µs            -
join_param[n=1000,sep='-']          131.75 µs        7.6 K    129.32 µs … 134.82 µs    132.23 µs    134.70 µs    134.76 µs            -
join_param[n=1000,sep=':']          135.62 µs        7.4 K    131.17 µs … 147.50 µs    136.68 µs    146.92 µs    147.21 µs            -
group: strings                                                                                                                  
join-baseline  ★                    376.07 ns        2.7 M    371.95 ns … 384.09 ns    378.96 ns    383.66 ns    383.87 ns     baseline
join-basic                          377.90 ns        2.6 M    365.89 ns … 382.65 ns    381.15 ns    382.55 ns    382.60 ns       ≈ same
concat                               10.62 µs       94.1 K      10.54 µs … 10.71 µs     10.65 µs     10.70 µs     10.71 µs 28.25× slower
```

## 💡 Tips

- Use `BenchContext.start()/end()` para isolar a seção crítica e evitar ruído de setup.
- Prefira `--profile smoke` durante o desenvolvimento; troque para `--profile thorough` antes de publicar números.
- Para logs, use `--no-color`.
