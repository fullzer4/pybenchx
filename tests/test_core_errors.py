from pybench.timing import BenchContext
from pybench.bench_model import Case
from pybench.params import make_variants as _make_variants
from pybench.overrides import apply_overrides


def test_make_variants_empty_params_and_kwargs_merge():
    c = Case(name="a", func=lambda **k: None, mode="func", args=(1,), kwargs={"x": 1}, params=None)
    vs = _make_variants(c)
    assert vs == [("a", (1,), {"x": 1})]


def test_apply_overrides_invalid_keys_go_to_kwargs():
    c = Case(name="a", func=lambda **k: None, mode="func")
    c2 = apply_overrides(c, {"foo": 1, "bar": True})
    assert c2.kwargs["foo"] == 1 and c2.kwargs["bar"] is True


def test_bench_context_multiple_start_end_pairs():
    b = BenchContext()
    # two disjoint intervals
    b.start(); b.end()
    first = b._elapsed_ns()
    b.start(); b.end()
    second = b._elapsed_ns()
    assert second >= first
