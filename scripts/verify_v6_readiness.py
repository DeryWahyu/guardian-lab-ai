"""Verify model/operational improvements without manufacturing release evidence."""

from datetime import datetime
import xml.etree.ElementTree as ET

import joblib
import numpy as np
import pandas as pd

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.rich_features import feature_matrix
from guardian_ml.shadow_gateway import verify_gateway_manifest
from audit_v6_indonesia_evidence import census
from audit_v6_human_review import inspect_pair
from experiment_v6_expanded_data import now, write_json
import experiment_v6_readiness as study
from v6_current_retrain_support import assert_original_recipe
from v6_development_support import assert_separated, transform_frame
from v6_indonesia_external_support import structure_masks
from v6_readiness_support import choose, decisions

OUTPUT = ROOT / "ml/reports/v6-readiness-verification.json"


def main():
    p, data, original = study.check()
    report = study.parent.read(study.REPORT)
    frozen = study.parent.read(study.RUN / "models-frozen.json")
    started = study.parent.read(study.RUN / "evaluation-started.json")
    if (
        checksum(study.RUN / "models-frozen.json") != report["models_freeze_sha256"]
        or started["models_sha256"] != report["models_freeze_sha256"]
    ):
        raise ValueError("readiness_model_replay_binding_changed")
    if choose(frozen["development"]) != report["selection"]:
        raise ValueError("readiness_selection_not_reproduced_from_tune")
    chronology = [
        data["prepared_at_utc"],
        frozen["frozen_at_utc"],
        started["started_at_utc"],
        report["completed_at_utc"],
    ]
    moments = [datetime.fromisoformat(x) for x in chronology]
    if moments != sorted(moments):
        raise ValueError("readiness_chronology_invalid")
    frames = []
    for part, a in data["assets"].items():
        frame = pd.read_parquet(ROOT / a["path"])
        if set(frame.partition) != {part} or not set(frame.training_source) <= set(
            p["allowed_sources"]
        ):
            raise ValueError("readiness_filtered_partition_invalid")
        frames.append(frame)
    assert_separated(frames)
    base_path = ROOT / frozen["records"]["baseline"]["artifact"]
    base = joblib.load(base_path)
    assert_original_recipe(base, original.bundle)
    for a in frozen["records"].values():
        study.parent.verify_files({a["artifact"]: a["sha256"]})
    expert_name = report["selection"]["diagnostic"]
    expert = joblib.load(ROOT / frozen["records"][expert_name]["artifact"])
    if expert["metadata"]["baseline_sha256"] != checksum(base_path):
        raise ValueError("private_expert_encoder_binding_changed")
    old_data = study.parent.read(study.parent.RUN / "data-frozen.json")
    old_report = study.parent.read(study.parent.REPORT)
    audit = {}
    for cohort, asset in old_data["tests"].items():
        frame, _ = transform_frame(pd.read_parquet(ROOT / asset["path"]))
        private = structure_masks(frame)["private_hosting"].to_numpy()
        path = study.RUN / (cohort + "-scores.npz")
        study.parent.verify_files(
            {
                path.relative_to(ROOT).as_posix(): report["scores"][
                    path.relative_to(ROOT).as_posix()
                ]
            }
        )
        scores = np.load(path)
        if not np.array_equal(private, scores["private"]) or not np.array_equal(
            scores[expert_name][~private], scores["baseline"][~private]
        ):
            raise ValueError("readiness_routing_changed_nonprivate_predictions")
        policies = {
            name: r["policies"]
            for name, r in frozen["records"].items()
            if name in scores
        }
        for name, old_name in (
            ("previous_current", "current_v6_recipe"),
            ("frozen_v6", "frozen_native"),
        ):
            points = {
                level: m["threshold"]
                for level, m in old_report["records"][old_name]["policies"].items()
            }
            policies[name] = {"general": points, "private": points}
        positive = frame.label.to_numpy() == 1
        for name, policy in policies.items():
            probability = scores[name]
            for level in ("warning", "high"):
                flags = decisions(probability, private, policy, level)
                counts = {
                    "tn": int((~positive & ~flags).sum()),
                    "fp": int((~positive & flags).sum()),
                    "fn": int((positive & ~flags).sum()),
                    "tp": int((positive & flags).sum()),
                }
                metric = report["cohorts"][cohort]["levels"][level][name]["overall"]
                if counts != metric["confusion_matrix"]:
                    raise ValueError("readiness_confusion_recount_failed")
                if positive.all():
                    if any(
                        metric[k] is not None
                        for k in ("accuracy", "precision", "fpr", "brier_score")
                    ):
                        raise ValueError("readiness_positive_only_metrics_invalid")
                elif (
                    abs(
                        np.mean((probability - positive.astype(float)) ** 2)
                        - metric["brier_score"]
                    )
                    > 1e-12
                ):
                    raise ValueError("routed_brier_must_use_real_probabilities")
        indices = np.linspace(0, len(frame) - 1, min(128, len(frame)), dtype=int)
        matrix = feature_matrix(base["encoder"], frame.core.iloc[indices])
        delta = float(
            np.max(
                np.abs(
                    study.score_matrix(joblib.load(base_path), matrix)
                    - scores["baseline"][indices]
                )
            )
        )
        private_indices = np.flatnonzero(private)
        if len(private_indices):
            private_indices = private_indices[
                np.linspace(
                    0,
                    len(private_indices) - 1,
                    min(128, len(private_indices)),
                    dtype=int,
                )
            ]
            pmatrix = feature_matrix(base["encoder"], frame.core.iloc[private_indices])
            expert_delta = float(
                np.max(
                    np.abs(
                        study.score_matrix(
                            joblib.load(
                                ROOT / frozen["records"][expert_name]["artifact"]
                            ),
                            pmatrix,
                        )
                        - scores[expert_name][private_indices]
                    )
                )
            )
        else:
            expert_delta = 0.0
        old_scores = np.load(study.parent.RUN / (cohort + "-predictions.npz"))
        if not np.array_equal(
            scores["previous_current"], old_scores["current_v6_recipe"]
        ) or not np.array_equal(scores["frozen_v6"], old_scores["frozen_native"]):
            raise ValueError("readiness_cached_reference_scores_changed")
        old_scores.close()
        if max(delta, expert_delta) > 1e-12:
            raise ValueError("readiness_saved_model_parity_failed")
        audit[cohort] = {
            "recounted_rows": len(frame),
            "base_replay_cases": len(indices),
            "private_replay_cases": len(private_indices),
            "base_max_delta": delta,
            "expert_max_delta": expert_delta,
        }
        scores.close()
    gateway = verify_gateway_manifest()
    load_path = ROOT / "ml/reports/v6-shadow-gateway-load-test.json"
    load = study.parent.read(load_path)
    if load["gateway_manifest_sha256"] != checksum(
        ROOT / "ml/policies/shadow-gateway-manifest.json"
    ) or load["script_sha256"] != checksum(
        ROOT / "scripts/load_test_shadow_gateway.py"
    ):
        raise ValueError("gateway_load_report_source_binding_changed")
    if load["model_sha256"] != original.manifest["bundle_sha256"]:
        raise ValueError("gateway_uses_different_model")
    for phase in load["phases"]:
        m = phase["gateway_counters"]
        if (
            m["inflight"]
            or m["peak_inflight"] > m["capacity"]
            or phase["prediction_parity_max_delta"] > 1e-12
        ):
            raise ValueError("gateway_load_bound_or_parity_failed")
    xml = study.RUN / "final-tests.xml"
    suites = list(ET.parse(xml).getroot().iter("testsuite"))
    tests = {
        key: sum(int(s.get(key, 0)) for s in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    if tests["tests"] < 274 or any(tests[k] for k in ("failures", "errors", "skipped")):
        raise ValueError("readiness_full_tests_incomplete")
    inputs = census(ROOT / "ml/data/indonesia-gold/input", ROOT / "ml/templates")
    review = inspect_pair(
        ROOT / "ml/data/v6-weighted-review-20261105/conflict-reviewer-a.csv",
        ROOT / "ml/data/v6-weighted-review-20261105/conflict-reviewer-b.csv",
    )
    study.check()
    license_path = ROOT / "ml/provenance/v6-readiness-license-screening.json"
    result = {
        "verified_at_utc": now(),
        "verification_source_sha256": checksum(__file__),
        "model_report_sha256": checksum(study.REPORT),
        "tests": tests,
        "test_report_sha256": checksum(xml),
        "chronology_verified": True,
        "all_filtered_partitions_separated": True,
        "excluded_sources_absent_from_fitting_and_all_development": p[
            "exclude_from_every_fit_and_development_partition"
        ],
        "sidecars_unchanged": len(data["exposure"]),
        "original_model_and_metadata_unchanged": True,
        "prediction_recounts_and_real_artifact_parity": audit,
        "gateway_manifest_sha256": checksum(
            ROOT / "ml/policies/shadow-gateway-manifest.json"
        ),
        "parent_runtime_manifest_sha256": gateway["parent_manifest_sha256"],
        "gateway_load_report_sha256": checksum(load_path),
        "license_audit_sha256": checksum(license_path),
        "indonesia_inputs": inputs,
        "development_human_review": review,
        "available_reviewers_user_reported": False,
        "commercial_clearance": False,
        "release_blockers": [
            "independent_indonesia_gold_and_two_reviewers_missing",
            "private_host_model_regressions_and_recall_target_unresolved",
            "upstream_rights_and_attribution_review_pending",
            "deployed_network_TLS_multiworker_load_and_shared_quota_not_tested",
        ],
        "production_ready": False,
    }
    write_json(OUTPUT, result)
    print(
        {
            "tests": tests,
            "verified_cohorts": len(audit),
            "gold_input_rows": sum(a["rows"] for a in inputs.values()),
            "review_pairs": review["complete_attested_pairs"],
            "production_ready": False,
        },
        flush=True,
    )


if __name__ == "__main__":
    main()
