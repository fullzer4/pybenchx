"""String manipulation benchmark examples used in documentation."""

from __future__ import annotations

from pybench import Bench, BenchContext, bench


@bench(name="join", n=1000, repeat=10)
def join(sep: str = ",") -> None:
    """Benchmark joining 100 short strings with the provided separator."""
    sep.join(str(i) for i in range(100))


@bench(name="join_param", params={"n": [100, 1000], "sep": ["-", ":"]}, repeat=10)
def join_param(n: int, sep: str = ",") -> None:
    """Join *n* strings with a configurable separator to exercise parameters."""
    sep.join(str(i) for i in range(n))


suite = Bench("strings")
# Suite/context style benchmarks for string workloads.


@suite.bench(name="join-baseline", baseline=True, n=1_000, repeat=10)
def join_baseline(ctx: BenchContext) -> None:
    """Baseline suite benchmark performing a fixed join."""
    seed = ",".join(str(i) for i in range(50))
    ctx.start()
    _ = ",".join([seed] * 5)
    ctx.end()


@suite.bench(name="join-basic", n=1_000, repeat=10)
def join_basic(ctx: BenchContext) -> None:
    """Suite benchmark joining a repeated small payload."""
    seed = ",".join(str(i) for i in range(50))
    ctx.start()
    _ = ",".join([seed] * 5)
    ctx.end()


@suite.bench(name="concat", n=1_000, repeat=10)
def concat(ctx: BenchContext) -> None:
    """Concatenate many small strings using repeated addition."""
    pieces = [str(i) for i in range(200)]
    ctx.start()
    buffer = ""
    for piece in pieces:
        buffer += piece
    ctx.end()
