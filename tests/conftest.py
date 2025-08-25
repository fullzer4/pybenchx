import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
import pybench.core as core_mod


@pytest.fixture(autouse=True)
def _isolate_global_registry():
    """Isolate global bench registry per test; keep DEFAULT_BENCH."""
    saved_benches = list(core_mod._GLOBAL_BENCHES)
    saved_default_cases = list(getattr(core_mod, "DEFAULT_BENCH")._cases)

    core_mod._GLOBAL_BENCHES.clear()
    core_mod._GLOBAL_BENCHES.append(core_mod.DEFAULT_BENCH)
    core_mod.DEFAULT_BENCH._cases.clear()
    try:
        yield
    finally:
        core_mod._GLOBAL_BENCHES.clear()
        core_mod._GLOBAL_BENCHES.extend(saved_benches)
        core_mod.DEFAULT_BENCH._cases.clear()
        core_mod.DEFAULT_BENCH._cases.extend(saved_default_cases)
