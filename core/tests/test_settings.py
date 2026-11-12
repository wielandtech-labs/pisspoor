import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load_settings(**env):
    base = {k: v for k, v in os.environ.items() if k not in {"SECRET_KEY", "DEBUG"}}
    return subprocess.run(
        [sys.executable, "-c", "import config.settings"],
        cwd=ROOT,
        env={**base, **env},
        capture_output=True,
        text=True,
    )


def test_startup_without_secret_key_fails_when_not_debug():
    result = _load_settings()
    assert result.returncode != 0
    assert "SECRET_KEY must be set" in result.stderr


@pytest.mark.parametrize("env", [{"DEBUG": "1"}, {"SECRET_KEY": "x"}])
def test_startup_succeeds_with_debug_or_a_secret_key(env):
    assert _load_settings(**env).returncode == 0
