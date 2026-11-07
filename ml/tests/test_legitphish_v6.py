"""External intake never visits targets, persists short secrets or reuses exposure."""

import importlib
import sys

import pandas as pd
import pytest

from guardian_ml.paths import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
external = importlib.import_module("evaluate_legitphish_v6")
sys.path.pop(0)


def test_publisher_labels_are_explicitly_inverted_and_unknown_labels_rejected():
    content = b"URL,ClassLabel\nhttps://example.org/,0\nhttps://example.com/,1\n"
    frame, _, counts = external.read_release(content)
    assert frame.label.tolist() == [1, 0]
    assert counts == {"0": 1, "1": 1}
    with pytest.raises(ValueError, match="unknown_legitphish_publisher_labels"):
        external.read_release(b"URL,ClassLabel\nhttps://example.org/,2\n")


def test_sensitive_path_assignment_is_excluded_instead_of_silently_changing_frozen_input():
    raw = pd.DataFrame(
        {
            "url": [
                "https://example.org/password=SHORTSECRET",
                "https://example.org/login?token=SHORTSECRET",
            ],
            "label": [1, 0],
        }
    )
    frame, counts = external.sanitize_intake(raw)
    assert len(frame) == 1 and frame.core.iloc[0] == "https://example.org/login"
    assert counts["privacy_assignment_excluded_label_1"] == 1
    assert "SHORTSECRET" not in frame.to_json()


def test_missing_label_is_quarantined_without_inventing_a_class():
    content = b"URL,ClassLabel\nhttps://example.org/,0\nhttps://example.com/,\n"
    frame, _, counts = external.read_release(content)
    assert frame.label.tolist() == [1]
    assert counts["missing_label_quarantined"] == 1
    assert "example.com" not in frame.to_json()


def test_conflicts_and_previously_exposed_domains_are_excluded():
    raw = pd.DataFrame(
        {
            "url": [
                "http://example.org/",
                "https://example.org/",
                "https://example.net/new",
                "https://example.com/novel",
            ],
            "label": [0, 1, 1, 0],
        }
    )
    frame, _ = external.sanitize_intake(raw)
    retained, counts = external.curate(frame, set(), {external.digest("example.net")})
    assert counts["conflicting_representations"] == 1
    assert counts["conflicting_rows"] == 2
    assert retained.group.tolist() == ["example.com"]


def test_representation_hash_exposure_blocks_scheme_variant():
    frame, _ = external.sanitize_intake(
        pd.DataFrame({"url": ["https://example.org/login"], "label": [1]})
    )
    prior = {external.representation_digest("http://example.org/login")}
    retained, _ = external.curate(frame, prior, set())
    assert retained.empty


def test_domain_cap_is_not_label_or_score_selection():
    raw = pd.DataFrame(
        {
            "url": [f"https://example.org/page-{index}" for index in range(10)],
            "label": [index % 2 for index in range(10)],
        }
    )
    frame, _ = external.sanitize_intake(raw)
    first, _ = external.curate(frame, set(), set(), cap=5)
    second, _ = external.curate(frame.assign(label=1 - frame.label), set(), set(), cap=5)
    assert len(first) == 5
    assert first.digest.tolist() == second.digest.tolist()


def test_download_redirect_cannot_follow_a_dataset_target(monkeypatch):
    class Response:
        status_code = 302
        headers = {"Location": "https://example.org/target"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return Response()

    monkeypatch.setattr(external.requests, "get", get)
    with pytest.raises(ValueError, match="unapproved_dataset_download_host"):
        external.download_bytes(
            {
                "download_url": "https://data.mendeley.com/public-files/test",
                "bytes": 5,
                "sha256": "invalid",
            }
        )
    assert calls == ["https://data.mendeley.com/public-files/test"]


def test_download_integrity_fails_before_csv_parsing(monkeypatch):
    class Response:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def raise_for_status(self):
            return None

        def iter_content(self, size):
            yield b"wrong"

    monkeypatch.setattr(external.requests, "get", lambda *args, **kwargs: Response())
    with pytest.raises(ValueError, match="dataset_download_integrity_mismatch"):
        external.download_bytes(
            {
                "download_url": "https://data.mendeley.com/public-files/test",
                "bytes": 5,
                "sha256": "invalid",
            }
        )
