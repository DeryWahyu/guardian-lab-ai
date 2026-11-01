import subprocess
import sys

import pytest

from guardian_ml.paths import ROOT


@pytest.mark.parametrize("run_id", ["../escape", "/absolute", "has space", "x" * 49])
def test_isolated_runner_rejects_unsafe_ids_before_processing_data(run_id):
    result = subprocess.run(
        [sys.executable, str(ROOT / "ml/run.py"), run_id, "dataset"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "Invalid run ID" in result.stderr
