"""Load only checksum-bound local v6 artifacts, without executing notebook code."""

from importlib.metadata import version
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from .metadata import checksum, psl_identity
from .paths import ROOT
from .rich_features import NUMERIC_COLUMNS, SCHEMA_VERSION, probabilities

INFERENCE_DEPENDENCIES = frozenset(
    {
        "joblib",
        "numpy",
        "pandas",
        "requests",
        "scikit-learn",
        "scipy",
        "tldextract",
        "threadpoolctl",
    }
)


class ArtifactRejected(ValueError):
    """Fixed reason codes only; paths or input values are not included."""


def workspace_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ArtifactRejected("invalid_artifact_relative_path")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ArtifactRejected("artifact_path_outside_workspace")
    return path


class RichArtifact:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        manifest_path = self.root / "ml/policies/shadow-serving-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["schema_version"] != SCHEMA_VERSION:
            raise ArtifactRejected("unsupported_feature_schema")
        if manifest["model_version"] != "notebook-url-core-v6":
            raise ArtifactRejected("unsupported_model_version")
        for relative, expected in manifest["source_hashes"].items():
            if checksum(workspace_path(self.root, relative)) != expected:
                raise ArtifactRejected("runtime_source_checksum_mismatch")
        frozen_path = workspace_path(self.root, manifest["frozen_metadata_path"])
        model_path = workspace_path(self.root, manifest["artifact_path"])
        if checksum(frozen_path) != manifest["frozen_metadata_sha256"]:
            raise ArtifactRejected("frozen_metadata_checksum_mismatch")
        frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
        if frozen["code_sha256"] != manifest["training_notebook_code_sha256"]:
            raise ArtifactRejected("training_code_binding_mismatch")
        if checksum(model_path) != manifest["bundle_sha256"]:
            raise ArtifactRejected("model_checksum_mismatch")
        if frozen["bundle_sha256"] != manifest["bundle_sha256"]:
            raise ArtifactRejected("model_manifest_mismatch")
        training_versions = frozen["metadata"]["versions"]
        expected_versions = manifest.get("inference_dependencies")
        if (
            not isinstance(expected_versions, dict)
            or set(expected_versions) != INFERENCE_DEPENDENCIES
            or any(
                training_versions.get(name) != value for name, value in expected_versions.items()
            )
        ):
            raise ArtifactRejected("inference_dependency_schema_mismatch")
        if {name: version(name) for name in expected_versions} != expected_versions:
            raise ArtifactRejected("dependency_versions_mismatch")
        if psl_identity() != manifest["psl"]:
            raise ArtifactRejected("offline_psl_mismatch")
        # The public manifest binds the binary produced by this workspace's own training.
        bundle = joblib.load(model_path)
        metadata = bundle["metadata"]
        if metadata != frozen["metadata"]:
            raise ArtifactRejected("embedded_metadata_mismatch")
        if metadata["version"] != manifest["model_version"]:
            raise ArtifactRejected("embedded_model_version_mismatch")
        config = metadata["config"]
        if (
            config["word_weight"] != 0.7
            or config["numeric_weight"] != 0.2
            or not config["exclude_scheme_from_all_model_features"]
        ):
            raise ArtifactRejected("unsupported_feature_weights")
        encoder = bundle["encoder"]
        if not all(isinstance(encoder.get(key), TfidfVectorizer) for key in ("char", "word")):
            raise ArtifactRejected("unsupported_text_encoder")
        if not isinstance(encoder.get("scaler"), StandardScaler):
            raise ArtifactRejected("unsupported_numeric_encoder")
        if encoder["scaler"].n_features_in_ != len(NUMERIC_COLUMNS):
            raise ArtifactRejected("numeric_feature_schema_mismatch")
        expected_features = (
            len(encoder["char"].vocabulary_)
            + len(encoder["word"].vocabulary_)
            + len(NUMERIC_COLUMNS)
        )
        for name in ("classifier", "calibrator"):
            estimator = bundle[name]
            if not isinstance(estimator, LogisticRegression):
                raise ArtifactRejected("unsupported_classifier")
            if not np.array_equal(estimator.classes_, [0, 1]):
                raise ArtifactRejected("unsupported_label_schema")
            if (
                not np.isfinite(estimator.coef_).all()
                or not np.isfinite(estimator.intercept_).all()
            ):
                raise ArtifactRejected("nonfinite_model_parameters")
        if bundle["classifier"].n_features_in_ != expected_features:
            raise ArtifactRejected("text_feature_schema_mismatch")
        if bundle["calibrator"].n_features_in_ != 1 or bundle["calibrator"].coef_[0, 0] <= 0:
            raise ArtifactRejected("unsupported_calibration")
        thresholds = metadata["thresholds"]
        if not 0 <= thresholds["warning"] <= 1 or not (
            thresholds["warning"] <= thresholds["high"] <= np.nextafter(1.0, 2.0)
        ):
            raise ArtifactRejected("invalid_decision_thresholds")
        if metadata["high_enabled"] != (thresholds["high"] <= 1):
            raise ArtifactRejected("high_policy_mismatch")
        if thresholds != manifest["thresholds"]:
            raise ArtifactRejected("threshold_manifest_mismatch")
        policy = manifest.get("decision_policy", {})
        if (
            not isinstance(policy, dict)
            or policy.get("version") != "v6-user-warning-0.5-20261107"
            or policy.get("thresholds") != {"warning": 0.5, "high": thresholds["high"]}
            or policy.get("selection") != "user_fixed_after_observed_benchmark"
            or policy.get("production_ready") is not False
        ):
            raise ArtifactRejected("decision_policy_mismatch")
        self.bundle = bundle
        self.metadata = metadata
        self.manifest = manifest
        self.decision_thresholds = dict(policy["thresholds"])
        self.decision_policy_version = policy["version"]

    def predict_cores(self, cores):
        values = probabilities(self.bundle, list(cores))
        if not np.isfinite(values).all() or (values < 0).any() or (values > 1).any():
            raise ArtifactRejected("nonfinite_prediction")
        return values
