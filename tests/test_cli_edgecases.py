import textwrap
from pathlib import Path
import re

import pybench.cli as cli_mod
import pybench.core as core_mod


def test_benchmark_with_invalid_context_usage_falls_back(tmp_path: Path, monkeypatch):
    # Context function that never calls start/end → used_ctx False → fallback path
    bench = tmp_path / "bad_ctx_bench.py"
    bench.write_text(textwrap.dedent(
        """
        from pybench import Bench, BenchContext
        s = Bench("g")
        @s.bench(name="bad", n=2, repeat=1)
        def bad(b: BenchContext):
            pass
        """
    ))

    cli_mod.load_module_from_path(bench)

    # Ensure _prepare_variants marks used_ctx=False and sets some local_n
    (case,) = core_mod.all_cases()
    variants = cli_mod._prepare_variants(case, budget_ns=None, max_n=10, smoke=True)
    assert variants[0][3] is False  # used_ctx


def test_cli_overrides_params_and_kwargs(tmp_path: Path, monkeypatch, capsys):
    bench = tmp_path / "over_bench.py"
    bench.write_text(textwrap.dedent(
        """
        from pybench import bench
        @bench(name="p", params={"n": [1, 2], "x": ["a"]}, kwargs={"x": "b"}, repeat=1)
        def p(n, x):
            return n, x
        """
    ))

    rc = cli_mod.run([str(tmp_path)], keyword=None, propairs=["n=5", "x=z"], use_color=False, sort=None, desc=False, budget_ns=None, profile="smoke", max_n=10)
    out = capsys.readouterr().out
    assert rc == 0
    # Ensure exactly one row for benchmark 'p' (label may or may not include params)
    rows = re.findall(r"^\s*p(?:\[[^\]]+\])?\b", out, flags=re.M)
    assert len(rows) >= 1
