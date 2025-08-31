import textwrap
from pathlib import Path

from pybench.timing import BenchContext, _pc_ns as _pc_ns_ref
from pybench.bench_model import Case
from pybench.runner import detect_used_ctx as _detect_used_ctx, infer_mode as _infer_mode, run_single_repeat as _run_single_repeat, calibrate_n as _calibrate_n
from pybench.params import make_variants as _make_variants
from pybench.overrides import apply_overrides
from pybench.reporters.table import format_table
import pybench.cli as cli_mod
from pybench.run_model import VariantResult, StatSummary
import pybench.timing as timing_mod


def test_infer_mode_by_annotation_and_name():
    # by annotation
    def f1(b: BenchContext):  # type: ignore[name-defined]
        pass

    # by name only
    def f2(b, x=1):
        return x

    # no context
    def f3(x=1):
        return x

    assert _infer_mode(f1) == "context"
    assert _infer_mode(f2) == "context"
    assert _infer_mode(f3) == "func"


def test_bench_context_start_end_accumulate(monkeypatch):
    t = {"now": 0}

    def fake_pc():
        t["now"] += 50
        return t["now"]

    # monkeypatch the timing module's clock
    monkeypatch.setattr(timing_mod, "_pc_ns", fake_pc)

    b = BenchContext()
    # end without start: no crash, no effect
    b.end()
    assert b._elapsed_ns() == 0

    # single start/end
    b.start(); b.end()
    assert b._elapsed_ns() == 50

    # nested start ignored
    b.start(); b.start(); b.end()
    assert b._elapsed_ns() == 100  # +50


def test_make_variants_and_precedence():
    c = Case(
        name="join_param",
        func=lambda n, sep=",": None,
        mode="func",
        args=(),
        kwargs={"sep": ","},
        params={"n": [100, 1000], "sep": ["-"]},
    )
    variants = _make_variants(c)
    names = [v[0] for v in variants]
    assert "join_param[n=100,sep='-']" in names
    assert "join_param[n=1000,sep='-']" in names
    # Ensure kwargs got overridden by params
    for _, _args, kw in variants:
        assert kw["sep"] == "-"


def test_apply_overrides_params_vs_kwargs():
    c = Case(
        name="case",
        func=lambda **kw: None,
        mode="func",
        n=10,
        repeat=2,
        warmup=1,
        group=None,
        kwargs={"x": 1},
        params={"p": [1, 2]},
        baseline=False,
    )
    overrides = {
        "n": 5,
        "repeat": 7,
        "warmup": 0,
        "group": "G",
        "baseline": True,
        "p": 99,       # param override
        "x": 3,        # kw override
    }
    c2 = apply_overrides(c, overrides)
    assert c2.n == 5 and c2.repeat == 7 and c2.warmup == 0
    assert c2.group == "G" and c2.baseline is True
    assert c2.params["p"] == [99]
    assert c2.kwargs["x"] == 3


def test_detect_used_ctx_true_and_false():
    def uses(b: BenchContext):
        b.start(); b.end()

    def not_uses(b: BenchContext):
        pass

    assert _detect_used_ctx(uses, (), {}) is True
    assert _detect_used_ctx(not_uses, (), {}) is False


def test_run_single_repeat_context_used_ctx(monkeypatch):
    # Each start/end adds +100 ns due to fake clock
    t = {"now": 0}

    def fake_pc():
        t["now"] += 100
        return t["now"]

    monkeypatch.setattr(timing_mod, "_pc_ns", fake_pc)

    def fn(b: BenchContext):
        b.start(); b.end()

    case = Case(name="c", func=fn, mode="context", n=5)
    per = _run_single_repeat(case, "c", (), {}, used_ctx=True, local_n=5)
    assert per == 100  # per-call ns


def test_run_single_repeat_context_fallback_loop_time(monkeypatch):
    # Clock: first call 0, second call n*100
    calls = {"i": 0}

    def fake_pc():
        i = calls["i"]
        calls["i"] += 1
        return 0 if i == 0 else 500  # for n=5 => 100 per call

    monkeypatch.setattr(timing_mod, "_pc_ns", fake_pc)

    def fn(b: BenchContext):
        pass  # no start/end used

    case = Case(name="c", func=fn, mode="context", n=5)
    per = _run_single_repeat(case, "c", (), {}, used_ctx=False, local_n=5)
    assert per == 100


def test_run_single_repeat_func_mode(monkeypatch):
    # Clock: first call 0, second call n*50
    calls = {"i": 0}

    def fake_pc():
        i = calls["i"]
        calls["i"] += 1
        return 0 if i == 0 else 250  # for n=5 => 50 per call

    monkeypatch.setattr(timing_mod, "_pc_ns", fake_pc)

    def fn():
        return None

    case = Case(name="f", func=fn, mode="func", n=5)
    per = _run_single_repeat(case, "f", (), {}, used_ctx=False, local_n=5)
    assert per == 50


def test_format_table_headers_groups_speedups_and_sorting():
    # Build three VariantResult entries to feed the table formatter
    r_base = VariantResult(name="base", group="G", n=1, repeat=3, baseline=True, stats=StatSummary(mean=200.0, median=200.0, stdev=0.0, min=200.0, max=200.0, p75=200.0, p99=200.0, p995=200.0))
    r_same = VariantResult(name="same", group="G", n=1, repeat=3, baseline=False, stats=StatSummary(mean=200.0, median=200.0, stdev=2.0, min=198.0, max=202.0, p75=201.0, p99=202.0, p995=202.0))
    r_fast = VariantResult(name="fast", group="G", n=1, repeat=3, baseline=False, stats=StatSummary(mean=100.0, median=100.0, stdev=0.0, min=100.0, max=100.0, p75=100.0, p99=100.0, p995=100.0))

    txt = format_table([r_base, r_same, r_fast], use_color=False, sort="time", desc=False)
    # Headers present
    assert "benchmark" in txt and "time (avg)" in txt and "vs base" in txt
    # Group heading and baseline marker
    assert "group: G" in txt
    assert "base  ★" in txt
    # Speedup strings
    assert "≈ same" in txt
    assert "2.00× faster" in txt

    # Sorting by group order
    r2 = VariantResult(name="other", group="A", n=1, repeat=1, baseline=False, stats=StatSummary(mean=300.0, median=300.0, stdev=0.0, min=300.0, max=300.0, p75=300.0, p99=300.0, p995=300.0))
    txt2 = format_table([r2, r_base], use_color=False, sort="group", desc=False)
    # Group A header should appear before G
    assert txt2.splitlines()[1].strip().startswith("group: A")


def test_prepare_variants_handles_warmup_exception(tmp_path: Path):
    bench_file = tmp_path / "warm_bench.py"
    bench_file.write_text(
        textwrap.dedent(
            """
            from pybench import bench, BenchContext
            did_warm = {"v": False}

            @bench(name="boom", n=1, repeat=1, warmup=1)
            def boom(b: BenchContext):
                # raise only on warmup (first ever call)
                if not did_warm["v"]:
                    did_warm["v"] = True
                    raise RuntimeError("warmup crash")
                b.start(); b.end()
            """
        )
    )

    # Load module as CLI would
    cli_mod.load_module_from_path(bench_file)

    # Find the registered case
    from pybench.bench_model import all_cases
    case = next(c for c in all_cases() if c.name == "boom")

    # Should not raise, despite the warmup raising once inside
    variants = cli_mod._prepare_variants(case, budget_ns=None, max_n=1000, smoke=False)
    assert variants and isinstance(variants[0], tuple)


def test_cli_end_to_end_smoke(tmp_path: Path, monkeypatch, capsys):
    # Create a small benchmark file with a baseline and variants
    bench_file = tmp_path / "mini_bench.py"
    bench_file.write_text(
        textwrap.dedent(
            """
            from pybench import bench, Bench, BenchContext

            @bench(name="func_case", n=1, repeat=2)
            def func_case():
                return 1

            suite = Bench("grp")

            @suite.bench(name="base", baseline=True, n=1, repeat=2)
            def base(b: BenchContext):
                b.start(); b.end()

            @suite.bench(name="fast", n=1, repeat=2)
            def fast(b: BenchContext):
                b.start(); b.end()

            @suite.bench(name="same", n=1, repeat=2)
            def same(b: BenchContext):
                b.start(); b.end()
            """
        )
    )

    # Deterministic per-call timing via monkeypatching the CLI's imported _run_single_repeat
    def fake_repeat(case, name, vargs, vkwargs, used_ctx, local_n):
        if name.endswith("base"):
            return 200.0
        if name.endswith("fast"):
            return 100.0
        if name.endswith("same"):
            return 198.0
        return 150.0

    monkeypatch.setattr(cli_mod, "_run_single_repeat", fake_repeat)

    rc = cli_mod.run([str(tmp_path)], keyword=None, propairs=[], use_color=False, sort="time", desc=False, budget_ns=None, profile="smoke", max_n=100)
    captured = capsys.readouterr().out

    assert rc == 0
    assert "cpu:" in captured and "runtime:" in captured
    assert "group: grp" in captured
    assert "base  ★" in captured
    assert "2.00× faster" in captured or "2.00× faster" in captured
    assert "≈ same" in captured
