"""Unit tests targeting error-handling paths in core helpers."""

from pybench.bench_model import Case
from pybench.overrides import apply_overrides
from pybench.params import make_variants as _make_variants
from pybench.timing import BenchContext


def test_make_variants_empty_params_and_kwargs_merge():
    """Parameter-free cases should yield a single variant with kwargs merged."""
    c = Case(
        name="a",
        func=lambda **k: None,
        mode="func",
        args=(1,),
        kwargs={"x": 1},
        params=None,
    )
    vs = _make_variants(c)
    assert vs == [("a", (1,), {"x": 1})]


def test_apply_overrides_invalid_keys_go_to_kwargs():
    """Unknown override keys should land in kwargs to preserve flexibility."""
    c = Case(name="a", func=lambda **k: None, mode="func")
    c2 = apply_overrides(c, {"foo": 1, "bar": True})
    assert c2.kwargs["foo"] == 1 and c2.kwargs["bar"] is True


def test_bench_context_multiple_start_end_pairs():
    """BenchContext should accumulate elapsed time across intervals."""
    b = BenchContext()
    # two disjoint intervals
    b.start()
    b.end()
    first = b._elapsed_ns()
    b.start()
    b.end()
    second = b._elapsed_ns()
    assert second >= first
