from __future__ import annotations

from pybench import bench, Bench, BenchContext


# Simple decorator style
@bench(name="join", n=1000, repeat=10)
def join(sep: str = ","):
    sep.join(str(i) for i in range(100))


@bench(name="join_param", params={"n": [100, 1000], "sep": ["-", ":"]}, repeat=10)
def join_param(n: int, sep: str = ","):
    sep.join(str(i) for i in range(n))


# Suite/context style
suite = Bench("strings")


@suite.bench(name="join-baseline", baseline=True, n=1_000, repeat=10)
def join_baseline(b: BenchContext):
    s = ",".join(str(i) for i in range(50))
    b.start()
    _ = ",".join([s] * 5)
    b.end()


@suite.bench(name="join-basic", n=1_000, repeat=10)
def join_basic(b: BenchContext):
    s = ",".join(str(i) for i in range(50))
    b.start()
    _ = ",".join([s] * 5)
    b.end()


@suite.bench(name="concat", n=1_000, repeat=10)
def concat(b: BenchContext):
    pieces = [str(i) for i in range(200)]
    b.start()
    s = ""
    for p in pieces:
        s += p
    b.end()
