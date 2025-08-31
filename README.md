# PyBench — precise microbenchmarks for Python

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

- Simple API: `@bench(...)` or suites with `Bench` and `BenchContext.start()/end()` para regiões críticas.
- Auto-discovery: `pybench <dir>` expande `**/*bench.py`.
- Parametrização: gere casos via `params={...}` (produto cartesiano) ou por caso com `args/kwargs`.
- Ajustes em runtime: `-P key=value` sobrescreve `n`, `repeat`, `warmup`, `group` e parâmetros custom.
- Timing sólido: clock monotônico, controle de GC, warmup, repeats, fast-path de contexto.
- Calibração esperta: por variante para atingir um budget de tempo.
- Tabela bonita: colunas alinhadas, percentis, iter/s, min…max, baseline e speedup vs. base.
- Cores sensíveis a TTY: `--no-color` para ambientes plain.

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

### 🎛️ CLI options que importam

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
  pybench examples/ --profile thorough  # ~1s budget, repeat=30
  pybench examples/ --profile smoke     # no calibration, repeat=3 (default)
  ```

### 📊 Output

Header includes CPU, Python, perf_counter clock info, total time, and profile. Table shows speed vs baseline with percent:

```
(pybench) $ pybench examples/
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
- Para CI ou logs, use `--no-color`.
