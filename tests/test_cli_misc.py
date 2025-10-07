"""CLI integration tests covering export and formatting behaviors."""

import textwrap
from pathlib import Path

import pybench.cli as cli_mod
import pybench.runner as runner_mod


def test_discover_only_bench_files(tmp_path: Path):
    """Only files ending with ``_bench.py`` should be discovered."""
    (tmp_path / "a_bench.py").write_text("# ok")
    (tmp_path / "b.txt").write_text("# nope")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c_bench.py").write_text("# ok")

    files = cli_mod.discover([str(tmp_path)])
    names = sorted(p.name for p in files)
    assert names == ["a_bench.py", "c_bench.py"]


def test_parse_ns_variants():
    """Clock budget strings should parse into integer nanoseconds."""
    assert cli_mod._parse_ns("300ms") == 300_000_000
    assert cli_mod._parse_ns("1s") == 1_000_000_000
    assert cli_mod._parse_ns("500000") == 500_000


def test_cli_no_files_returns_nonzero(tmp_path: Path, capsys):
    """Running on folders without benches should return non-zero."""
    rc = cli_mod.run(
        [str(tmp_path)],
        keyword=None,
        propairs=[],
        use_color=False,
        sort=None,
        desc=False,
        budget_ns=None,
        profile=None,
        max_n=100,
    )
    out = capsys.readouterr().out
    assert rc == 1
    assert "No benchmark files found." in out


def test_cli_no_color_omits_ansi(tmp_path: Path, monkeypatch, capsys):
    """The ``--no-color`` flag removes ANSI escapes from output."""
    bench = tmp_path / "t_bench.py"
    bench.write_text(textwrap.dedent(
        """
        from pybench import bench
        @bench(name="x", n=1, repeat=1)
        def x():
            return 1
        """
    ))

    monkeypatch.setattr(runner_mod, "run_single_repeat", lambda *a, **k: 100.0)

    rc = cli_mod.run(
        [str(tmp_path)],
        keyword=None,
        propairs=[],
        use_color=False,
        sort=None,
        desc=False,
        budget_ns=None,
        profile="smoke",
        max_n=10,
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "\x1b[" not in out


def test_run_export_all_creates_files(tmp_path: Path, monkeypatch, capsys):
    """Exporting ``all`` formats should materialize every target file."""
    monkeypatch.chdir(tmp_path)

    bench = tmp_path / "export_bench.py"
    bench.write_text(textwrap.dedent(
        """
        from pybench import bench

        @bench(name="sample", n=1, repeat=1)
        def sample():
            return 42
        """
    ))

    monkeypatch.setattr(runner_mod, "run_single_repeat", lambda *a, **k: 123.0)

    rc = cli_mod.run(
        [str(tmp_path)],
        keyword=None,
        propairs=[],
        use_color=False,
        sort=None,
        desc=False,
        budget_ns=None,
        profile="smoke",
        max_n=10,
        export=["all"],
    )
    assert rc == 0

    root = tmp_path / ".pybenchx" / "exports"
    json_files = list((root / "json").glob("*.json"))
    md_files = list((root / "markdown").glob("*.md"))
    csv_files = list((root / "csv").glob("*.csv"))
    chart_files = list((root / "chart").glob("*.html"))

    assert json_files, "JSON export missing"
    assert md_files, "Markdown export missing"
    assert csv_files, "CSV export missing"
    assert chart_files, "Chart export missing"
