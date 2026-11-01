"""Development-only diagnosis, temporal data gate and untrained CNN invariants."""

import json

import numpy as np
import pandas as pd
import pytest

from guardian_ml.cnn_readiness import require_training_readiness
from guardian_ml.exposure_v10 import completed_v10_intake
from guardian_ml.paths import ROOT
from guardian_ml.recall_audit import error_flags, error_slices


def test_development_audit_cannot_consume_test_labels():
    frame = pd.DataFrame({"partition": ["test"]})
    with pytest.raises(ValueError, match="development_tune"):
        error_slices(frame, {}, {}, pd.DataFrame())


def test_error_counts_are_separate_from_labels_and_plain_url_is_not_safe():
    cores = ["https://example.org/page", "https://example.net/login"]
    flags = error_flags(cores)
    frame = pd.DataFrame(
        {
            "partition": ["tune"] * 2,
            "digest": ["a", "b"],
            "group": ["example.org", "example.net"],
            "label": [1, 0],
            "training_source": ["fixture"] * 2,
        }
    )
    original = frame.label.copy()
    result, cases = error_slices(frame, {"model": [0.1, 0.9]}, {"model": 0.5}, flags)
    assert result["model"]["all"]["confusion_matrix"] == {"tn": 0, "fp": 1, "fn": 1, "tp": 0}
    assert list(cases.model_error) == ["false_negative", "false_positive"]
    assert flags.lexically_plain.iloc[0]
    assert frame.label.equals(original)


def test_historical_negatives_and_positive_only_data_cannot_unlock_training():
    evidence = {
        "development_error_audit_complete": True,
        "intake_integrity_verified": True,
        "new_holdout_frozen_before_training": True,
        "holdout_domains_disjoint": True,
        "holdout_labels_traceable": True,
        "holdout_period_verified": False,
        "new_holdout_benign": 0,
        "new_holdout_phishing": 2,
    }
    with pytest.raises(ValueError, match="holdout_period_verified"):
        require_training_readiness(evidence)
    evidence.update(holdout_period_verified=True, new_holdout_benign=400, new_holdout_phishing=200)
    assert require_training_readiness(evidence)


def test_tokenizer_is_deterministic_scheme_free_and_reports_truncation():
    pytest.importorskip("torch")
    from guardian_ml.character_cnn import CUT, tokenize

    tokens, truncated = tokenize(["http://example.org/page", "https://example.org/page"], 64)
    assert np.array_equal(tokens[0], tokens[1]) and not truncated.any()
    long, truncated = tokenize(["https://example.org/" + "section/" * 30 + "tail"], 64)
    assert truncated[0] and int((long == CUT).sum()) == 1
    assert list(long[0, -4:]) == [ord(x) + 3 for x in "tail"]
    with pytest.raises(ValueError, match="canonical_core"):
        tokenize(["https://example.org/?private=value"])


def test_cnn_masks_padding_and_loads_only_local_tensor_weights(tmp_path):
    torch = pytest.importorskip("torch")
    from guardian_ml.character_cnn import CharacterCNN, tokenize

    torch.set_num_threads(2)
    model = CharacterCNN(embedding=8, channels=4).eval()
    tokens, _ = tokenize(["https://example.org/page"], 64)
    padded = torch.cat([tokens, torch.zeros((1, 32), dtype=torch.long)], dim=1)
    with torch.no_grad():
        expected = model(tokens)
        assert torch.allclose(expected, model(padded), atol=1e-6)
    model(tokens).sum().backward()
    assert model.embedding.weight.grad[0].eq(0).all()
    path = tmp_path / "synthetic-untrained-test.pt"
    torch.save(model.state_dict(), path)
    restored = CharacterCNN(embedding=8, channels=4).eval()
    restored.load_state_dict(torch.load(path, weights_only=True))
    with torch.no_grad():
        assert torch.equal(expected, restored(tokens))
    with pytest.raises(ValueError, match="empty_token"):
        model(torch.zeros((1, 64), dtype=torch.long))


def test_real_intake_is_bound_and_does_not_claim_cnn_training():
    path = ROOT / "ml/runs/notebook-recall-cnn-v10/reports/public-intake-manifest.json"
    if not path.exists():
        pytest.skip("Requires completed local v10 source intake")
    verified = completed_v10_intake(ROOT)
    assert verified is not None
    assert not verified["provenance"]["cnn_trained"]
    report = json.loads(path.read_text())
    assert not report["cnn_training_ready"] and report["new_temporal_benign_rows"] == 0
    assert not report["new_cases_predicted"] and not report["target_urls_visited"]
    data = pd.read_parquet(ROOT / next(iter(report["outputs"].values()))["path"])
    assert data.digest.is_unique and data.groupby("group").partition.nunique().max() == 1
    assert not list((path.parent.parent / "artifacts").glob("*.pt"))
