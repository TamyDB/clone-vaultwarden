import hashlib
import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "checksums.py"


@pytest.fixture
def checksums():
    spec = importlib.util.spec_from_file_location("checksums", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lists_each_file_with_its_sha256(checksums, tmp_path):
    (tmp_path / "b.bin").write_bytes(b"segundo")
    (tmp_path / "a.bin").write_bytes(b"primeiro")

    lines = checksums.write_checksums(tmp_path).read_text(encoding="utf-8").splitlines()

    assert lines == [
        f"{hashlib.sha256(b'primeiro').hexdigest()}  a.bin",
        f"{hashlib.sha256(b'segundo').hexdigest()}  b.bin",
    ]


def test_does_not_hash_its_own_output_on_rerun(checksums, tmp_path):
    (tmp_path / "a.bin").write_bytes(b"x")
    checksums.write_checksums(tmp_path)
    checksums.write_checksums(tmp_path)
    assert len((tmp_path / "SHA256SUMS").read_text(encoding="utf-8").splitlines()) == 1


def test_uses_lf_line_endings_on_every_platform(checksums, tmp_path):
    (tmp_path / "a.bin").write_bytes(b"x")
    assert b"\r" not in checksums.write_checksums(tmp_path).read_bytes()


def test_empty_folder_is_an_error(checksums, tmp_path):
    with pytest.raises(SystemExit):
        checksums.write_checksums(tmp_path)


@pytest.mark.skipif(shutil.which("sha256sum") is None, reason="sha256sum não disponível")
def test_output_is_accepted_by_sha256sum(checksums, tmp_path):
    (tmp_path / "cofre").write_bytes(b"binario" * 1000)
    checksums.write_checksums(tmp_path)
    result = subprocess.run(  # noqa: S603
        ["sha256sum", "-c", "SHA256SUMS"],  # noqa: S607
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
