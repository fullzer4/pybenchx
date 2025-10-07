"""Param sweep example benches used in documentation."""

from pybench import BenchContext, bench


@bench(
    name="param_sweep",
    n=1,
    repeat=10,
    params={"a": [0, 1, 2, 3], "b": [0, 1, 2, 3, 4]},
)
def param_sweep(a: int, b: int) -> int:
    """Tiny workload proportional to the sum of two parameters."""
    total = 0
    for value in range((a + b) % 7 + 1):
        total += value
    return total


@bench(name="baseline", baseline=True, n=1, repeat=10)
def baseline(ctx: BenchContext) -> None:
    """Minimal baseline benchmark using context mode."""
    ctx.start()
    ctx.end()


@bench(name="variant", n=1, repeat=10)
def variant(ctx: BenchContext) -> None:
    """Variant benchmark mirroring the baseline for comparison."""
    ctx.start()
    ctx.end()
