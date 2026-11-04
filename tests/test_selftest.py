import subprocess
import sys

from cofre import selftest
from cofre.selftest import SELF_TEST_FLAG, run_self_test


def test_self_test_passes():
    assert run_self_test() == 0


def test_self_test_reports_failure(monkeypatch):
    monkeypatch.setattr(selftest, "generate_password", lambda: 1 / 0)
    assert run_self_test() == 1


def test_self_test_does_not_touch_user_data(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert run_self_test() == 0
    assert list(tmp_path.iterdir()) == []


def test_flag_runs_self_test_without_starting_the_interface():
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "cofre", SELF_TEST_FLAG],
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0
