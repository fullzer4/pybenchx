# Contributing to **pybenchx**

Thanks for your interest in improving **pybenchx** — a tiny, precise microbenchmarking framework for Python. This guide explains how to set up your environment, propose changes, and ship great contributions with a smooth DX.

> TL;DR
> - Use **Nix** or **uv** for a reproducible dev env.
> - Follow **Conventional Commits**.
> - Keep PRs small and focused, with tests and docs.
> - Version comes from **Git tags** (via `hatch-vcs`), e.g. `v1.2.3`.
> - CI builds & publishes to PyPI when you push a tag `v*`.

---

## Code of Conduct

This project adheres to the [Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).  
By participating, you are expected to uphold this code. Please report unacceptable behavior privately.

---

## Prerequisites

- **Git** ≥ 2.40
- **Python** 3.10 · 3.11 · 3.12 · 3.13
- **uv** ≥ 0.8.0 (from [Astral](https://docs.astral.sh/uv/))
- **Nix** (optional, recommended for reproducible dev shell; with flakes)

---

## Getting Started

Clone the repo:
```bash
git clone https://github.com/fullzer4/pybenchx
cd pybenchx
```

### Option A — Nix (recommended)

```bash
# Default: Python 3.12
nix develop

# Or pick a version quickly:
nix develop .#py310
nix develop .#py311
nix develop .#py312
nix develop .#py313
```

### Option B — System Python + uv

1) Install Python 3.10+ and [uv](https://docs.astral.sh/uv/).  
2) Create the dev environment:
```bash
uv sync --all-extras --dev
```
3) Validate the CLI:
```bash
uv run pybench --help
```

## Development workflow

1. Create a feature branch: `git checkout -b feat/<short-topic>`.
2. Make focused commits following [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) (`feat:`, `fix:`, `docs:`, etc.).
3. Keep pull requests small and scoped to one change; open an issue first for large shifts.
4. Run the quality checks below before pushing.
5. Open a draft PR early if you want feedback; mark it ready after all checks are green.

## Quality checks

Everything we run in CI is available locally:

```bash
ruff check .
pytest
uv run pybench run examples/ --profile smoke --vs main  # optional regression sniff test
```

- `ruff check .` enforces lint/style; use `ruff check --fix` for autofixes where supported.
- `pytest` powers the unit and CLI tests (`tests/`).
- When you modify reporters or calibration logic, add or update tests so behavior is locked in.
- For CLI changes, extend the integration tests in `tests/test_cli_*.py` and consider adding sample output fixtures when helpful.

## Documentation & site

The docs live under `docs/` (Astro + Starlight):

```bash
cd docs
npm install
npm run dev   # http://localhost:4321

npm run lint  # optional link and content checks
```

- Keep `README.md` and `docs/src/content/docs/*.mdx` in sync when you add features.
- Add runnable examples under `examples/` when introducing new capabilities—docs link to them directly.

## Writing good benchmarks

- Benchmarks should be deterministic: seed random data, avoid network/disk IO, and keep setup work outside the timed region (or use `BenchContext`).
- Prefer small fixtures over large datasets so quick profiles stay fast.
- Document tricky cases inline with comments; future contributors will thank you.

## Release process (maintainers)

1. Update `CHANGELOG.md` and docs, then receive approvals.
2. Tag the release: `git tag -a v1.2.0 -m "v1.2.0"`.
3. Push the tag: `git push origin v1.2.0`.
4. CI (GitHub Actions) builds wheels/sdist and publishes to PyPI automatically.
5. Create a GitHub release with highlights and link to docs.

If you spot an issue post-release, cut a new patch version (`vX.Y.Z+1`)—versions are derived from tags via `hatch-vcs`.

## Before you submit

- ✅ Tests, lint, and (if affected) docs build locally.
- ✅ Added/updated tests cover the behavior change.
- ✅ Docs/README mention any user-facing switches or flags.
- ✅ PR description references related issues and explains the motivation.
- ✅ No stray `.pybenchx/` artifacts or other generated files are committed.

## Security Policy

Please report vulnerabilities privately: **gabrielpelizzaro@gmail.com**  
We follow responsible disclosure: do not open public issues for sensitive reports.

---

## License

**MIT** — see `LICENSE`.

---

## Acknowledgements

Thanks for helping make **pybenchx** faster and better!
