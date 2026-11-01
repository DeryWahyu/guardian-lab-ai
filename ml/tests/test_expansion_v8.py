"""Archive integrity, fit-only vocabulary and source-regression selection guards."""

from copy import copy
import io
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
import pytest

from guardian_ml.tr_op_source import partition
from guardian_ml.v8_selection import choose_candidate, fit_text_encoder
from guardian_ml.zip_ranges import decode_member, MAX_MEMBER_BYTES
from guardian_ml.zip_ranges import fetch_member


def archive_member():
    handle = io.BytesIO()
    with ZipFile(handle, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("fixture/info.txt", "https://example.org/login")
    blob = handle.getvalue()
    with ZipFile(io.BytesIO(blob)) as archive:
        info = archive.infolist()[0]
    return blob, info


def test_zip_text_member_is_verified_against_crc_and_declared_size():
    blob, info = archive_member()
    assert decode_member(blob, info) == b"https://example.org/login"
    corrupted = copy(info)
    corrupted.CRC ^= 1
    with pytest.raises(ValueError, match="zip_crc_mismatch"):
        decode_member(blob, corrupted)
    oversized = copy(info)
    oversized.file_size = MAX_MEMBER_BYTES + 1
    with pytest.raises(ValueError, match="zip_member_too_large"):
        decode_member(blob, oversized)
    with pytest.raises(ValueError, match="truncated_zip"):
        decode_member(blob[:32], info)


def test_selection_does_not_allow_macro_average_to_override_worst_source():
    results = [
        {"name": "high_average", "source_guard_passed": True, "worst_first_score": [0.4, 0.8, 0.9]},
        {
            "name": "stronger_worst",
            "source_guard_passed": True,
            "worst_first_score": [0.5, 0.6, 0.8],
        },
        {"name": "regression", "source_guard_passed": False, "worst_first_score": [0.9, 0.9, 0.99]},
    ]
    challenger, decision = choose_candidate(results)
    assert challenger["name"] == decision["development_selection"] == "stronger_worst"
    challenger, decision = choose_candidate([results[2]])
    assert decision["development_selection"] == "retain_frozen_v6"
    assert not decision["challenger_passed_source_guard"]


def test_vocabulary_does_not_fit_heldout_tokens_or_allow_test_partition():
    cores = ["https://example.org/login/account"] * 16
    numeric = np.ones((16, 33), dtype=np.float32)
    encoder = fit_text_encoder(cores, ["fixture"] * 16, numeric, partition="fit")
    before = dict(encoder["word"].vocabulary_)
    encoder["word"].transform(["heldoutuniquemarker"])
    assert before == encoder["word"].vocabulary_
    assert "heldoutuniquemarker" not in encoder["word"].vocabulary_
    with pytest.raises(ValueError, match="fitting_partition"):
        fit_text_encoder(cores, ["fixture"] * 16, numeric, partition="test")


def test_domain_partition_is_deterministic_and_has_all_predeclared_roles():
    roles = [partition("tenant" + str(i) + ".org") for i in range(1000)]
    assert roles == [partition("tenant" + str(i) + ".org") for i in range(1000)]
    assert set(roles) == {"fit", "tune", "calibration", "threshold", "new_test"}


def test_nonrange_http_response_is_rejected_before_reading_whole_archive():
    class Response:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def raise_for_status(self):
            pass

        @property
        def raw(self):
            raise AssertionError("Must reject unbounded archive before reading")

    class Session:
        def get(self, *args, **kwargs):
            assert kwargs["stream"]
            return Response()

    blob, info = archive_member()
    with pytest.raises(ValueError, match="range_not_honored"):
        fetch_member(Session(), "https://dataset.example.org/archive.zip", info, len(blob))


def test_real_v8_artifact_and_completed_exposure_are_bound():
    import json
    import joblib
    from guardian_ml.metadata import checksum
    from guardian_ml.paths import ROOT
    from guardian_ml.structural_features import probabilities
    from guardian_ml.exposure_v8 import completed_v8_inventory

    path = ROOT / "ml/runs/notebook-tfidf-logistic-v8/reports/frozen-v8.json"
    if not path.exists():
        pytest.skip("Requires local trained v8 artifact")
    frozen = json.loads(path.read_text())
    model = path.parent.parent / "artifacts/url-core-logistic-v8.joblib"
    assert checksum(model) == frozen["bundle_sha256"]
    bundle = joblib.load(model)
    repair_path = path.parent / "presentation-repair.json"
    if repair_path.exists():
        repair = json.loads(repair_path.read_text())
        payload = joblib.hash(
            {k: v for k, v in bundle.items() if k != "metadata"}, hash_name="sha1"
        )
        assert payload == repair["estimator_encoder_calibrator_payload_joblib_sha1_before"]
        assert payload == repair["estimator_encoder_calibrator_payload_joblib_sha1_after"]
    values = probabilities(bundle, ["http://example.org/login", "https://example.org/login"])
    assert values[0] == values[1] and np.isfinite(values).all()
    assert completed_v8_inventory(ROOT) is not None
    assert bundle["metadata"]["selection_decision"] == frozen["selection_decision"]
