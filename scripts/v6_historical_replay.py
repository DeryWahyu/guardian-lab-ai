"""Read-only parity replay of frozen artifacts after later exposure is appended.

This is not an intake, novelty, fitting or model-selection entry point. Historical
exposure may grow; every historically bound file must still exist unchanged.
The original experiment's stricter training-time inventory guard is untouched.
"""

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
import experiment_v6_segmented as study


def verify_append_only_inventory(expected, current):
    if any(current.get(name) != value for name, value in expected.items()):
        raise ValueError("historical_exposure_removed_or_modified")
    return sorted(current.keys() - expected.keys())


def load_segmented_for_parity():
    frozen = study.read(study.RUN / "cache-frozen.json")
    if (
        frozen["protocol_sha256"] != checksum(study.PROTOCOL)
        or frozen["amendment_sha256"] != checksum(study.AMENDMENT)
        or frozen["source_hashes"] != study.bindings()
    ):
        raise ValueError("historical_sources_or_protocol_changed")
    study.old_state()
    if (
        checksum(study.previous.RUN / "selected-frozen.json")
        != frozen["previous_selection_sha256"]
    ):
        raise ValueError("historical_previous_selection_changed")
    for item in frozen["assets"].values():
        for path_key, hash_key in (
            ("path", "sha256"),
            ("input_path", "input_sha256"),
            ("matrix_path", "matrix_sha256"),
            ("extra_path", "extra_sha256"),
        ):
            if path_key in item and checksum(ROOT / item[path_key]) != item[hash_key]:
                raise ValueError("historical_cache_binding_changed")
    if checksum(ROOT / frozen["encoder_path"]) != frozen["encoder_sha256"]:
        raise ValueError("historical_encoder_changed")
    for item in (frozen["intake"], frozen["phishbench"]):
        if item and study.check_intake(ROOT / item["path"]) != item:
            raise ValueError("historical_intake_changed")
    for name, sha in frozen["observed_test_bindings"].items():
        if checksum(ROOT / name) != sha:
            raise ValueError("historical_test_binding_changed")
    verify_append_only_inventory(
        frozen["all_current_sidecars"],
        {
            path.relative_to(ROOT).as_posix(): checksum(path)
            for path in sorted((ROOT / "ml/data/exposure-sidecars").glob("*.sqlite"))
        },
    )
    selected = study.read(study.RUN / "selected-frozen.json")
    if checksum(study.RUN / "cache-frozen.json") != selected["cache_sha256"]:
        raise ValueError("historical_selection_changed")
    for record in selected["records"].values():
        if checksum(ROOT / record["artifact"]) != record["artifact_sha256"]:
            raise ValueError("historical_artifact_changed")
    return frozen, selected
