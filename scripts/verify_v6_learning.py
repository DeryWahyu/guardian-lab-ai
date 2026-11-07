"""Audit chronology, all prior exposure, actual isolation and saved predictions."""

from datetime import datetime
import json
import sqlite3
import xml.etree.ElementTree as ET

import joblib
import numpy as np
import pandas as pd

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.rich_artifact import RichArtifact
from evaluate_legitphish_v6 import digest
from evaluate_v6_indonesia_external import verify_files
from experiment_v6_expanded_data import now, write_json
import experiment_v6_learning as study
from v6_development_support import (
    assert_separated,
    predict_bundle,
    representation_digest,
)
from v6_learning_support import choose, nested_fit


def main():
    p, state, cache, intake = study.check()
    selected = study.read(study.RUN / "selected-frozen.json")
    report = study.read(study.REPORT)
    started = study.read(study.RUN / "evaluation-started.json")
    selection_sha = checksum(study.RUN / "selected-frozen.json")
    if (
        started["selection_sha256"] != selection_sha
        or report["selection_freeze_sha256"] != selection_sha
    ):
        raise ValueError("learning_evaluation_selection_binding_changed")
    times = [
        intake["frozen_at_utc"],
        state["prepared_at_utc"],
        selected["frozen_at_utc"],
        started["started_at_utc"],
        report["completed_at_utc"],
    ]
    moments = [datetime.fromisoformat(t) for t in times]
    if moments != sorted(moments):
        raise ValueError("learning_chronology_invalid")
    names = [c["name"] for c in p["candidates"] if c["name"] in selected["results"]]
    decision = choose(selected["results"], names)
    if decision != selected["selection"] or decision != report["selection"]:
        raise ValueError("learning_selection_not_reproducible_from_tune")
    verify_files(report["score_bindings"])
    prediction_recounts = {}
    for cohort, result in report["cohorts"].items():
        asset_path = (
            intake["assets"][cohort]["path"]
            if cohort in intake["assets"]
            else "ml/data/v6-indonesia-external-20261106/global.parquet"
        )
        data = pd.read_parquet(ROOT / asset_path)
        predictions = np.load(study.RUN / (cohort + "-predictions.npz"))
        recount = {}
        for name in predictions.files:
            scores = predictions[name]
            if (
                len(scores) != len(data)
                or not np.isfinite(scores).all()
                or np.any((scores < 0) | (scores > 1))
            ):
                raise ValueError("learning_saved_predictions_invalid")
            threshold = (
                RichArtifact().manifest["thresholds"]["warning"]
                if name == "active_v6"
                else selected["records"][name]["thresholds"]["0.01"]["threshold"]
            )
            positive = data.label.to_numpy() == 1
            flagged = scores >= threshold
            counts = {
                "tp": int((positive & flagged).sum()),
                "fn": int((positive & ~flagged).sum()),
                "fp": int((~positive & flagged).sum()),
                "tn": int((~positive & ~flagged).sum()),
            }
            if counts != result["results"]["all"][name]["confusion_matrix"]:
                raise ValueError(
                    "learning_report_counts_disagree_with_saved_predictions"
                )
            indices = np.linspace(0, len(data) - 1, min(128, len(data)), dtype=int)
            if len(indices):
                if name == "active_v6":
                    replay = RichArtifact().predict_cores(data.core.iloc[indices])
                else:
                    replay = predict_bundle(
                        joblib.load(ROOT / selected["records"][name]["artifact"]),
                        data.core.iloc[indices],
                    )
                delta = float(np.max(np.abs(scores[indices] - replay)))
                if delta > 1e-12:
                    raise ValueError(
                        "learning_saved_scores_disagree_with_reloaded_artifact"
                    )
            else:
                delta = 0.0
            recount[name] = {
                "rows": len(data),
                "confusion_matrix_verified": True,
                "distributed_replay_cases": len(indices),
                "max_delta": delta,
            }
        predictions.close()
        prediction_recounts[cohort] = recount
    frames = [pd.read_parquet(ROOT / a["path"]) for a in intake["assets"].values()]
    novel = pd.concat(frames, ignore_index=True)
    assert_separated(frames)
    urls = set(novel.digest) | set(novel.representation_digest)
    domains = set(novel.group.map(digest))
    audit = {}
    prior = {
        **intake["prior_exposure_hashes"],
        **intake["actual_prior_identity_bindings"],
    }
    verify_files(prior)
    latest = ROOT / "ml/data/v6-indonesia-external-20261106/frozen.json"
    if (
        checksum(latest)
        != "86eca8bfa572edfd53d584df88c17c6b3e0e6db923bdb6bf158abbfc29014ca2"
    ):
        raise ValueError("learning_previous_external_freeze_changed")
    reserved = study.read(latest)["assets"]["reserved"]
    verify_files({reserved["path"]: reserved["sha256"]})
    if reserved["rows"] != 169393 or reserved["path"] not in prior:
        raise ValueError("learning_previous_reserve_not_fully_audited")
    for name in prior:
        path = ROOT / name
        if path.suffix == ".sqlite":
            with sqlite3.connect(
                path.resolve().as_uri() + "?mode=ro", uri=True
            ) as conn:
                u = sum(
                    value in urls
                    for (value,) in conn.execute("SELECT value FROM url_hashes")
                )
                d = sum(
                    value in domains
                    for (value,) in conn.execute("SELECT value FROM domain_hashes")
                )
        else:
            old = pd.read_parquet(path, columns=["core", "group", "digest"])
            u = len(urls & (set(old.digest) | set(old.core.map(representation_digest))))
            d = len(domains & set(old.group.map(digest)))
        if u or d:
            raise ValueError("learning_novel_data_overlaps_prior_exposure")
        audit[name] = {"url_or_representation_overlap": u, "domain_overlap": d}
    verify_files(
        {
            intake["supported_path"]: intake["supported_sha256"],
            intake["sidecar"]["path"]: intake["sidecar"]["sha256"],
        }
    )
    supported = pd.read_parquet(ROOT / intake["supported_path"])
    publisher_counts = {}
    for source, rows in supported.groupby("training_source"):
        raw_counts = intake["audit"][source]["label_counts"]
        supported_counts = {
            str(label): int(rows.label.eq(label).sum()) for label in (0, 1)
        }
        publisher_counts[source] = {
            "raw_label_counts": raw_counts,
            "supported_label_counts": supported_counts,
            "unsupported_by_label": {
                label: raw_counts[label] - supported_counts[label]
                for label in ("0", "1")
            },
            "label_0": "benign",
            "label_1": "phishing",
        }
    with sqlite3.connect(
        (ROOT / intake["sidecar"]["path"]).resolve().as_uri() + "?mode=ro", uri=True
    ) as conn:
        registered_urls = {v for (v,) in conn.execute("SELECT value FROM url_hashes")}
        registered_domains = {
            v for (v,) in conn.execute("SELECT value FROM domain_hashes")
        }
    if (
        not (set(supported.digest) | set(supported.representation_digest))
        <= registered_urls
        or not set(supported.group.map(digest)) <= registered_domains
    ):
        raise ValueError("learning_exposure_registry_incomplete")
    fit = pd.read_parquet(ROOT / cache["assets"]["fit"]["input_path"])
    tune = pd.read_parquet(ROOT / cache["assets"]["tune"]["input_path"])
    nested, parity = {}, {}
    previous_groups = set()
    for fraction in p["learning_curve"]["fractions"]:
        subset = nested_fit(fit, fraction, p["learning_curve"]["salt"])
        if not previous_groups <= set(subset.group):
            raise ValueError("learning_curve_not_nested")
        previous_groups = set(subset.group)
        name = "control" if fraction == 1 else "curve_" + str(int(fraction * 100))
        if len(subset) != selected["records"][name]["fit_rows"]:
            raise ValueError("learning_curve_fitting_count_changed")
        nested[name] = {"rows": len(subset), "groups": int(subset.group.nunique())}
    probes = tune.core.iloc[:128]
    for name, record in selected["records"].items():
        verify_files({record["artifact"]: record["sha256"]})
        bundle = joblib.load(ROOT / record["artifact"])
        first = predict_bundle(bundle, probes)
        second = predict_bundle(joblib.load(ROOT / record["artifact"]), probes)
        delta = float(np.max(np.abs(first - second)))
        if delta > 1e-12 or record["saved_model_parity_max_delta"] > 1e-12:
            raise ValueError("learning_artifact_parity_failed")
        parity[name] = {"cases": len(probes), "max_delta": delta}
    xml = study.RUN / "final-tests.xml"
    suites = list(ET.parse(xml).getroot().iter("testsuite"))
    tests = {
        key: sum(int(s.attrib.get(key, 0)) for s in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    if tests["tests"] < 221 or any(tests[k] for k in ("failures", "errors", "skipped")):
        raise ValueError("learning_test_suite_incomplete")
    test_manifest = study.read(study.RUN / "test-run-manifest.json")
    for filename, expected in test_manifest["source_reports"].items():
        if checksum(study.RUN / filename) != expected:
            raise ValueError("learning_original_junit_report_changed")
    if test_manifest["aggregate"] != tests:
        raise ValueError("learning_merged_test_counts_changed")
    active = RichArtifact()
    if (
        active.manifest["bundle_sha256"]
        != "f332bcbf7665955677e17daa73c487a7e1572a18d7f465b87e73caaa72e06319"
        or active.manifest["frozen_metadata_sha256"]
        != "4d2e6955af24d0507abce7bdfb65c7af7637183d3e26af75beaaa733846a2fb5"
    ):
        raise ValueError("learning_original_v6_changed")
    if report["production_ready"] or report["test_used_for_selection"]:
        raise ValueError("learning_report_scope_changed")
    result = {
        "verified_at_utc": now(),
        "report_sha256": checksum(study.REPORT),
        "verifier_sha256": checksum(__file__),
        "test_report_sha256": checksum(xml),
        "test_run_manifest": test_manifest,
        "tests": tests,
        "chronology_verified": True,
        "selection_replayed_using_tune_only": True,
        "all_supported_rows_registered": len(supported),
        "publisher_sanitization_counts": publisher_counts,
        "novel_rows": len(novel),
        "novelty_audit": audit,
        "nested_learning_curve": nested,
        "saved_model_parity": parity,
        "saved_prediction_recounts_and_replay": prediction_recounts,
        "all_169393_previous_reserved_rows_preserved": True,
        "original_v6_binary_metadata_and_thresholds_unchanged": True,
        "production_ready": False,
    }
    write_json(ROOT / "ml/reports/v6-learning-verification.json", result)
    print(
        json.dumps(
            {
                "tests": tests,
                "novel_rows": len(novel),
                "audited_exposures": len(audit),
                "parity_artifacts": len(parity),
                "production_ready": False,
            }
        )
    )


if __name__ == "__main__":
    main()
