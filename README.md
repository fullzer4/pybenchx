# PyBench — fast, precise microbenchmarks for Python

[![CI](https://github.com/fullzer4/pybenchx/actions/workflows/ci.yml/badge.svg)](https://github.com/fullzer4/pybenchx/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pybenchx?label=PyPI)](https://pypi.org/project/pybenchx/)
[![Python Versions](https://img.shields.io/pypi/pyversions/pybenchx.svg)](https://pypi.org/project/pybenchx/)
[![License](https://img.shields.io/github/license/fullzer4/pybenchx.svg)](LICENSE)

Measure small, focused snippets with minimal boilerplate, auto-discovery, smart calibration, and a clean CLI (command: `pybench`).

Run benchmarks with one command:

```bash
pybench examples/ [-k keyword] [-P key=value ...]
```

## ✨ Highlights

- Simple API: `@bench(...)` or suites with `Bench` and `BenchContext.start()/end()` for critical sections.
- Auto-discovery: `pybench <dir>` expands `**/*bench.py`.
- Parameterization: generate cases via `params={...}` (cartesian product) or per-case `args/kwargs`.
- Runtime tweaks: `-P key=value` overrides `n`, `repeat`, `warmup`, `group`, and custom params.
- Sound timing: monotonic high-res clock, GC control, warmup, repeats, context fast-path.
- Smart calibration: per-variant auto-calibration to hit a time budget.
- Pretty table: aligned columns, percentiles, iter/s, min…max, group headers, baseline and speedup vs. base.
- TTY-aware colors: `--no-color` for plain environments.

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
  pybench examples/
  ```
- Filter by name
  ```bash
  pybench examples/ -k join
  ```
- Override params at runtime
  ```bash
  pybench examples/ -P repeat=5 -P n=10000
  ```

### 🎛️ CLI options that matter

- Disable color
  ```bash
  pybench examples/ --no-color
  ```
- Sorting
  ```bash
  pybench examples/ --sort time --desc
  ```
- Time budget per variant (calibration)
  ```bash
  pybench examples/ --budget 300ms     # total per variant; split across repeats
  pybench examples/ --max-n 1000000    # cap calibrated n
  ```
- Profiles
  ```bash
  pybench examples/ --profile fast      # ~150ms budget, repeat=10
  pybench examples/ --profile thorough  # ~1s budget, repeat=30
  pybench examples/ --profile smoke     # no calibration, repeat=3
  ```

### 📊 Output

Header includes CPU, Python, perf_counter clock info, total time, and mode. Table shows speed vs baseline with percent:

```
(pybench) [fullzer4@archlinux pybenchx]$ pybench examples/
cpu: x86_64
runtime: python 3.12.5 (x86_64-linux) | perf_counter: res=1.0e-09s, mono=True
time: 21.722s | mode: default, budget=0.300s, max-n=1000000, smoke=False
benchmark                          time (avg)       iter/s              (min … max)          p75          p99         p995      vs base
join                                 11.72 µs       85.3 K      10.61 µs … 13.64 µs     12.16 µs     13.52 µs     13.58 µs            -
join_param[n=100,sep='-']            11.94 µs       83.8 K      10.56 µs … 13.61 µs     12.43 µs     13.56 µs     13.59 µs            -
join_param[n=100,sep=':']            11.55 µs       86.6 K      10.58 µs … 12.33 µs     12.21 µs     12.33 µs     12.33 µs            -
join_param[n=1000,sep='-']          118.69 µs        8.4 K    108.67 µs … 134.28 µs    121.52 µs    133.57 µs    133.93 µs            -
join_param[n=1000,sep=':']          121.14 µs        8.3 K    108.99 µs … 157.25 µs    123.28 µs    154.39 µs    155.82 µs            -
group: strings                                                                                                                  
join-baseline  ★                    429.42 ns        2.3 M    380.26 ns … 484.32 ns    452.78 ns    482.04 ns    483.18 ns     baseline
join-basic                          417.29 ns        2.4 M    383.02 ns … 471.58 ns    428.28 ns    468.33 ns    469.95 ns 1.03× faster (2.9%)
concat                                8.58 µs      116.6 K        7.88 µs … 9.84 µs      8.84 µs      9.80 µs      9.82 µs 19.97× slower (95.0%)
```

## 💡 Tips

- Use `BenchContext.start()/end()` to isolate the critical section and avoid setup noise.
- Prefer `--profile fast` during development; switch to `--profile thorough` before publishing numbers.
- For CI or logs, use `--no-color`.
