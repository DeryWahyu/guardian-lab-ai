"""Install the checksum-bound v6 GitHub Release asset; never download datasets."""

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tempfile
from zipfile import BadZipFile, ZipFile

import requests

ROOT = Path(__file__).resolve().parents[1]
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verified_members(data, distribution, runtime):
    """Authenticate the archive and exact members before writing any bytes."""
    if len(data) > MAX_ARCHIVE_BYTES or len(data) != distribution["archive_bytes"]:
        raise ValueError("archive_size_mismatch")
    if digest(data) != distribution["archive_sha256"]:
        raise ValueError("archive_checksum_mismatch")
    expected = {
        runtime["artifact_path"]: runtime["bundle_sha256"],
        runtime["frozen_metadata_path"]: runtime["frozen_metadata_sha256"],
    }
    if set(distribution["members"]) != set(expected):
        raise ValueError("distribution_member_schema_mismatch")
    for name, record in distribution["members"].items():
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
            raise ValueError("unsafe_archive_path")
        if (
            record["sha256"] != expected[name]
            or not 0 < record["bytes"] <= MAX_ARCHIVE_BYTES
        ):
            raise ValueError("distribution_runtime_binding_mismatch")
    try:
        with ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) != len(expected) or {info.filename for info in infos} != set(
                expected
            ):
                raise ValueError("unexpected_archive_members")
            result = {}
            for info in infos:
                record = distribution["members"][info.filename]
                if info.is_dir() or info.file_size != record["bytes"]:
                    raise ValueError("archive_member_size_mismatch")
                payload = archive.read(info)
                if (
                    len(payload) != record["bytes"]
                    or digest(payload) != expected[info.filename]
                ):
                    raise ValueError("archive_member_checksum_mismatch")
                result[info.filename] = payload
            return result
    except BadZipFile:
        raise ValueError("invalid_archive_or_crc") from None


def download(distribution):
    url = distribution["download_url"]
    prefix = "https://github.com/DeryWahyu/guardian-lab-ai/releases/download/"
    if not url.startswith(prefix):
        raise ValueError("unsupported_distribution_origin")
    chunks = []
    total = 0
    with requests.get(url, stream=True, timeout=(10, 60)) as response:
        response.raise_for_status()
        for chunk in response.iter_content(1 << 16):
            total += len(chunk)
            if total > min(MAX_ARCHIVE_BYTES, distribution["archive_bytes"]):
                raise ValueError("download_too_large")
            chunks.append(chunk)
    return b"".join(chunks)


def install(data, distribution, runtime, root=ROOT):
    root = Path(root).resolve()
    members = verified_members(data, distribution, runtime)
    destinations = {}
    for relative, payload in members.items():
        target = (root / relative).resolve()
        if not target.is_relative_to(root) or target == root:
            raise ValueError("artifact_path_outside_workspace")
        if target.exists() and digest(target.read_bytes()) != digest(payload):
            raise ValueError("existing_artifact_differs_backup_before_installing")
        destinations[target] = payload
    for target, payload in destinations.items():
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
            temporary.replace(target)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive", type=Path, help="Use the published ZIP downloaded manually"
    )
    args = parser.parse_args()
    distribution = json.loads((ROOT / "ml/policies/v6-distribution.json").read_text())
    runtime = json.loads(
        (ROOT / "ml/policies/shadow-runtime-manifest.json").read_text()
    )
    present = [
        ROOT / runtime[name] for name in ("artifact_path", "frozen_metadata_path")
    ]
    correct = all(
        path.is_file() and digest(path.read_bytes()) == expected
        for path, expected in zip(
            present, (runtime["bundle_sha256"], runtime["frozen_metadata_sha256"])
        )
    )
    if not correct or args.archive is not None:
        data = args.archive.read_bytes() if args.archive else download(distribution)
        install(data, distribution, runtime)
    from guardian_ml.rich_artifact import RichArtifact

    artifact = RichArtifact()
    print(
        json.dumps(
            {
                "status": "verified",
                "model": artifact.metadata["version"],
                "artifact_sha256": artifact.manifest["bundle_sha256"],
                "thresholds": artifact.metadata["thresholds"],
                "mode": "shadow",
                "production_ready": False,
            }
        )
    )


if __name__ == "__main__":
    main()
