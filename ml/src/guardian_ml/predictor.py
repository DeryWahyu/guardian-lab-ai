"""Trusted local bundle loader and offline URL/QR prediction."""

from __future__ import annotations

import json
import sys

import joblib
import pandas as pd

from .evaluation import apply_calibration
from .features import feature_frame, SCHEMA, VERSION
from .metadata import checksum, environment
from .paths import ARTIFACTS, REPRESENTATION, ROOT
from .preprocessing import prepare_url, InvalidUrl


class Predictor:
    def __init__(self, directory=ARTIFACTS):
        # Only load training artifacts we trust; checksums do not make arbitrary
        # user-uploaded pickle/joblib artifacts safe to deserialize.
        manifest = json.loads((directory / "manifest.json").read_text())
        if manifest["bundle_filename"] != "url-core-v1.joblib":
            raise ValueError("Unsupported artifact filename")
        path = directory / manifest["bundle_filename"]
        if checksum(path) != manifest["bundle_sha256"]:
            raise ValueError("Artifact checksum mismatch")
        current = environment()
        if current["dependencies"] != manifest["environment"]["dependencies"]:
            raise ValueError("Artifact dependency mismatch")
        if current["psl"] != manifest["environment"]["psl"]:
            raise ValueError("Offline PSL mismatch")
        if manifest["feature_schema"] != SCHEMA or manifest["feature_schema_version"] != VERSION:
            raise ValueError("Feature schema mismatch")
        if manifest["representation_version"] != REPRESENTATION:
            raise ValueError("Representation mismatch")
        for name in ("preprocessing.py", "features.py", "models.py", "evaluation.py"):
            relative = "ml/src/guardian_ml/" + name
            if checksum(ROOT / relative) != manifest["source_hashes"][relative]:
                raise ValueError("Inference implementation mismatch")
        self.bundle = joblib.load(path)
        self.manifest = manifest

    def predict(self, url, input_type="URL"):
        if input_type not in ("URL", "QR"):
            raise ValueError("Invalid input type")
        parsed = prepare_url(url)
        candidate = self.bundle["candidate"]
        features = feature_frame([parsed.core])
        raw = candidate.predict(pd.Series([parsed.core]), features)
        probability = float(apply_calibration(self.bundle["calibrator"], raw)[0])
        thresholds = self.manifest["thresholds"]
        risk = (
            "HIGH"
            if probability >= thresholds["high"]
            else ("MEDIUM" if probability >= thresholds["low"] else "LOW")
        )
        return {
            "status": "complete",
            "input_type": input_type,
            "target_redacted": parsed.core,
            "defanged_target": parsed.core.replace("http", "hxxp", 1).replace(".", "[.]"),
            "phishing_probability": probability,
            "risk_score": round(probability * 100),
            "risk_level": risk,
            "model_name": self.manifest["model_name"],
            "model_version": self.manifest["model_version"],
            "feature_schema_version": VERSION,
            "sanitizer_version": REPRESENTATION,
            "calibration_version": "heldout-v1-" + self.bundle["calibrator"]["method"],
            "thresholds": thresholds,
            "deployment_status": self.manifest["deployment_status"],
            "limitations": [
                "URL-only; does not inspect pages, redirects, downloads, or QRIS merchants.",
                "Query and fragment are excluded; parameter-only threats may be missed.",
                "Probability is calibrated to research data, not live Guardian Lab traffic.",
                "Low risk is not a guarantee of safety; Indonesia/2026 validation is pending.",
            ],
        }


def main():
    # stdin avoids encouraging credentials in shell command history.
    try:
        value = json.loads(sys.stdin.readline(32769))
        result = Predictor().predict(value["url"], value.get("input_type", "URL"))
        print(json.dumps(result))
    except InvalidUrl as error:
        print(json.dumps({"status": "invalid_input", "reason": str(error)}))
        raise SystemExit(2) from None
    except (KeyError, ValueError, TypeError, FileNotFoundError):
        print(json.dumps({"status": "unavailable_or_invalid_request"}))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
