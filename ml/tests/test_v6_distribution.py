"""Release installation authenticates synthetic archive bytes before writing."""

import importlib.util
import io
from zipfile import ZipFile

import pytest

from guardian_ml.paths import ROOT

spec = importlib.util.spec_from_file_location(
    "install_v6_model", ROOT / "scripts/install_v6_model.py"
)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def fixture_archive(extra=None):
    runtime = {
        "artifact_path": "ml/runs/v6/artifacts/model.joblib",
        "frozen_metadata_path": "ml/runs/v6/reports/frozen.json",
        "bundle_sha256": installer.digest(b"synthetic-model"),
        "frozen_metadata_sha256": installer.digest(b"synthetic-metadata"),
    }
    members = {
        runtime["artifact_path"]: b"synthetic-model",
        runtime["frozen_metadata_path"]: b"synthetic-metadata",
    }
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
        if extra:
            archive.writestr(extra, b"unexpected")
    data = buffer.getvalue()
    distribution = {
        "archive_bytes": len(data),
        "archive_sha256": installer.digest(data),
        "members": {
            name: {"bytes": len(payload), "sha256": installer.digest(payload)}
            for name, payload in members.items()
        },
    }
    return data, distribution, runtime


def test_verified_release_installs_exact_files_and_is_idempotent(tmp_path):
    data, distribution, runtime = fixture_archive()
    installer.install(data, distribution, runtime, tmp_path)
    installer.install(data, distribution, runtime, tmp_path)
    assert (tmp_path / runtime["artifact_path"]).read_bytes() == b"synthetic-model"
    assert len(list(tmp_path.rglob("*.*"))) == 2


@pytest.mark.parametrize("corruption", ["checksum", "binding", "size"])
def test_corrupt_or_unbound_release_is_rejected_before_writing(tmp_path, corruption):
    data, distribution, runtime = fixture_archive()
    if corruption == "checksum":
        data = data[:-1] + bytes([data[-1] ^ 1])
    elif corruption == "binding":
        distribution["members"][runtime["artifact_path"]]["sha256"] = "0" * 64
    else:
        distribution["archive_bytes"] += 1
    with pytest.raises(ValueError):
        installer.install(data, distribution, runtime, tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("extra", ["../../outside.joblib", "extra.txt"])
def test_unexpected_zip_member_cannot_be_written(tmp_path, extra):
    data, distribution, runtime = fixture_archive(extra=extra)
    with pytest.raises(ValueError, match="unexpected_archive_members"):
        installer.install(data, distribution, runtime, tmp_path)
    assert not list(tmp_path.iterdir())


def test_existing_different_artifact_is_preserved(tmp_path):
    data, distribution, runtime = fixture_archive()
    path = tmp_path / runtime["artifact_path"]
    path.parent.mkdir(parents=True)
    path.write_bytes(b"existing-model")
    with pytest.raises(ValueError, match="existing_artifact_differs"):
        installer.install(data, distribution, runtime, tmp_path)
    assert path.read_bytes() == b"existing-model"
    assert not (tmp_path / runtime["frozen_metadata_path"]).exists()
