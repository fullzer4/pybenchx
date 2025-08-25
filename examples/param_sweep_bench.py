from pybench import bench, BenchContext

# Synthetic param sweep: 4 * 5 = 20 variants for a single case; duplicate 4 times => 80 variants

@bench(name="param_sweep", n=1, repeat=10, params={"a": [0, 1, 2, 3], "b": [0, 1, 2, 3, 4]})
def param_sweep(a: int, b: int):
    # tiny work proportional to (a+b)
    s = 0
    for _ in range((a + b) % 7 + 1):
        s += _
    return s


# Context mode baseline and variant
@bench(name="baseline", baseline=True, n=1, repeat=10)
def baseline(b: BenchContext):
    b.start(); b.end()

@bench(name="variant", n=1, repeat=10)
def variant(b: BenchContext):
    b.start(); b.end()
