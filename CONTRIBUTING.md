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

## Security Policy

Please report vulnerabilities privately: **gabrielpelizzaro@gmail.com**  
We follow responsible disclosure: do not open public issues for sensitive reports.

---

## License

**MIT** — see `LICENSE`.

---

## Acknowledgements

Thanks for helping make **pybenchx** faster and better!
