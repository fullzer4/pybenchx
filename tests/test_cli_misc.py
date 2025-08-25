import textwrap
from pathlib import Path

import pybench.cli as cli_mod


def test_discover_only_bench_files(tmp_path: Path):
    (tmp_path / "a_bench.py").write_text("# ok")
    (tmp_path / "b.txt").write_text("# nope")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c_bench.py").write_text("# ok")

    files = cli_mod.discover([str(tmp_path)])
    names = sorted(p.name for p in files)
    assert names == ["a_bench.py", "c_bench.py"]


def test_parse_ns_variants():
    assert cli_mod._parse_ns("300ms") == 300_000_000
    assert cli_mod._parse_ns("1s") == 1_000_000_000
    assert cli_mod._parse_ns("500000") == 500_000


def test_cli_no_files_returns_nonzero(tmp_path: Path, capsys):
    rc = cli_mod.run([str(tmp_path)], keyword=None, propairs=[], use_color=False, sort=None, desc=False, budget_ns=None, profile=None, max_n=100)
    out = capsys.readouterr().out
    assert rc == 1
    assert "No benchmark files found." in out


def test_cli_no_color_omits_ansi(tmp_path: Path, monkeypatch, capsys):
    bench = tmp_path / "t_bench.py"
    bench.write_text(textwrap.dedent(
        """
        from pybench import bench
        @bench(name="x", n=1, repeat=1)
        def x():
            return 1
        """
    ))

    # Make runs deterministic and quick
    monkeypatch.setattr(cli_mod, "_run_single_repeat", lambda *a, **k: 100.0)

    rc = cli_mod.run([str(tmp_path)], keyword=None, propairs=[], use_color=False, sort=None, desc=False, budget_ns=None, profile="smoke", max_n=10)
    out = capsys.readouterr().out
    assert rc == 0
    assert "\x1b[" not in out  # no ANSI
