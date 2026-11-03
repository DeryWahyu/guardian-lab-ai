"""Build the reproducible v6 release ZIP containing only model and frozen metadata."""

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
TAG = "v6-shadow-20261103"
NAME = "guardian-lab-v6-shadow.zip"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "ml/data/github-publication" / NAME
    )
    args = parser.parse_args()
    runtime = json.loads(
        (ROOT / "ml/policies/shadow-runtime-manifest.json").read_text()
    )
    members = {}
    for path, expected in [
        (runtime["artifact_path"], runtime["bundle_sha256"]),
        (runtime["frozen_metadata_path"], runtime["frozen_metadata_sha256"]),
    ]:
        data = (ROOT / path).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("original_v6_artifact_checksum_mismatch")
        members[path] = data
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(
        args.output, "w", compression=ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path, data in sorted(members.items()):
            info = ZipInfo(path, date_time=(2026, 11, 3, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=ZIP_DEFLATED, compresslevel=9)
    data = args.output.read_bytes()
    distribution = {
        "schema_version": "v6-release-distribution-v1",
        "repository": "DeryWahyu/guardian-lab-ai",
        "release_tag": TAG,
        "asset_name": NAME,
        "download_url": f"https://github.com/DeryWahyu/guardian-lab-ai/releases/download/{TAG}/{NAME}",
        "archive_bytes": len(data),
        "archive_sha256": hashlib.sha256(data).hexdigest(),
        "members": {
            path: {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
            for path, payload in members.items()
        },
        "datasets_included": False,
        "noncommercial_research_only": True,
        "serving_mode": "shadow_only",
        "production_ready": False,
    }
    path = ROOT / "ml/policies/v6-distribution.json"
    path.write_bytes((json.dumps(distribution, indent=2) + "\n").encode())
    print(
        json.dumps(
            {
                "asset": str(args.output),
                "bytes": len(data),
                "sha256": distribution["archive_sha256"],
                "members": len(members),
            }
        )
    )


if __name__ == "__main__":
    main()
