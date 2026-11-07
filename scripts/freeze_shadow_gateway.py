"""Bind gateway sources and dependencies to the current shadow runtime manifest."""

from importlib.metadata import version
import json

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.shadow_gateway import SOURCE_FILES, GATEWAY_DEPENDENCIES
from experiment_v6_expanded_data import now, write_json


def main():
    core_path = ROOT / "ml/policies/shadow-serving-manifest.json"
    core = json.loads(core_path.read_text())
    write_json(
        ROOT / "ml/policies/shadow-gateway-manifest.json",
        {
            "schema_version": "shadow-gateway-v1",
            "created_at_utc": now(),
            "parent_manifest_sha256": checksum(core_path),
            "source_hashes": {n: checksum(ROOT / n) for n in sorted(SOURCE_FILES)},
            "inference_dependencies": core["inference_dependencies"],
            "gateway_dependencies": {
                n: version(n) for n in sorted(GATEWAY_DEPENDENCIES)
            },
            "production_ready": False,
        },
    )
    print("Gateway source manifest saved; bound to current runtime manifest")


if __name__ == "__main__":
    main()
