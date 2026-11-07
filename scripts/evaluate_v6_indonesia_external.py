"""Pinned external evaluation and .id proxy audit; never trains or promotes a model."""

import argparse
import io
import json

import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.rich_artifact import RichArtifact
from evaluate_legitphish_v6 import collect_exposure, digest, write_sidecar
from experiment_v6_development import paired_intervals
from experiment_v6_expanded_data import curate_new, now, write_json
from intake_v6_expansion import sanitize_source
from v6_development_support import predict_bundle, representation_digest
from v6_indonesia_external_support import (
    audit_human_inputs,
    coverage,
    diagnostic_metrics,
    structure_masks,
)
from v6_pinned_download import download_pinned

PROTOCOL = ROOT / "ml/reports/v6-indonesia-external-20261106-protocol.json"
AMENDMENT = ROOT / "ml/reports/v6-indonesia-external-schema-amendment.json"
DATA = ROOT / "ml/data/v6-indonesia-external-20261106"
RUN = ROOT / "ml/runs/v6-indonesia-external-20261106"
REPORT = ROOT / "ml/reports/v6-indonesia-external-evaluation.json"
SIDECAR = (
    ROOT / "ml/data/exposure-sidecars/mendeley-vfs-indonesia-external-20261106.sqlite"
)
OLD = ROOT / "ml/runs/v6-segmented-20261105"
SOURCES = [
    "scripts/evaluate_v6_indonesia_external.py",
    "scripts/v6_indonesia_external_support.py",
    "scripts/v6_pinned_download.py",
    "scripts/intake_v6_expansion.py",
    "scripts/evaluate_legitphish_v6.py",
    "scripts/experiment_v6_expanded_data.py",
    "scripts/v6_development_support.py",
    "scripts/v6_diagnostic_support.py",
    "scripts/experiment_v6_development.py",
    "scripts/evaluate_v6_quality.py",
    "scripts/audit_v6_human_review.py",
    "ml/src/guardian_ml/preprocessing.py",
    "ml/src/guardian_ml/evaluation.py",
]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify_files(bindings):
    for name, expected in bindings.items():
        if checksum(ROOT / name) != expected:
            raise ValueError("external_evaluation_binding_changed")


def prior_identities(urls, domains):
    old = read(OLD / "cache-frozen.json")
    verify_files(old["source_hashes"])
    bindings = dict(old["observed_test_bindings"])
    for item in old["assets"].values():
        if "input_path" in item:
            bindings[item["input_path"]] = item["input_sha256"]
    for intake in (old["intake"], old["phishbench"]):
        for item in intake["data"]["partitions"].values():
            bindings[item["path"]] = item["sha256"]
    verify_files(bindings)
    # Real identities from current fitting/calibration/threshold/tune and all eight tests.
    for name in bindings:
        frame = pd.read_parquet(ROOT / name, columns=["core", "group", "digest"])
        urls.update(frame.digest)
        urls.update(representation_digest(core) for core in frame.core)
        domains.update(digest(group) for group in frame.group)
    return bindings


def intake():
    if DATA.exists() or SIDECAR.exists():
        raise ValueError("external_intake_must_not_overwrite_exposure")
    protocol, amendment = read(PROTOCOL), read(AMENDMENT)
    if checksum(PROTOCOL) != amendment["parent_sha256"]:
        raise ValueError("external_parent_protocol_changed")
    for item in protocol["models"].values():
        verify_files({item["artifact"]: item["sha256"]})
    verify_files(
        {
            "ml/runs/v6-segmented-20261105/cache-frozen.json": "590200ed4e9c4ea3731307fee379fdba80ed0f77d9f94415e7fbfa5bb63daa37",
            "ml/runs/v6-segmented-20261105/selected-frozen.json": "1200b13901865735dc64610f2609c79dcf154f6482a77422cad3f45eddc58a68",
        }
    )
    RUN.mkdir(parents=True, exist_ok=True)
    bindings = {name: checksum(ROOT / name) for name in SOURCES}
    started = {
        "started_at_utc": now(),
        "protocol_sha256": checksum(PROTOCOL),
        "amendment_sha256": checksum(AMENDMENT),
        "source_hashes": bindings,
    }
    write_json(RUN / "intake-started.json", started)
    print(
        "Auditing registry, every sidecar and actual current development/test identities",
        flush=True,
    )
    urls, domains, exposure = collect_exposure()
    identities = prior_identities(urls, domains)
    content = download_pinned(protocol["source"])
    raw = pd.read_csv(
        io.BytesIO(content),
        usecols=[amendment["url_column"], amendment["label_column"]],
    )
    counts = {
        str(k): int(v)
        for k, v in raw[amendment["label_column"]].value_counts(dropna=False).items()
    }
    if (
        counts != amendment["label_counts"]
        or len(raw) != protocol["source"]["publisher_rows"]
    ):
        raise ValueError("external_publisher_schema_changed")
    print("Sanitizing publisher data in memory; no target requests", flush=True)
    supported, audit = sanitize_source(
        raw,
        protocol["source"]["id"],
        amendment["url_column"],
        amendment["label_column"],
    )
    supported["label"] = supported.publisher_label.map(amendment["label_mapping"])
    if supported.label.isna().any():
        raise ValueError("external_label_mapping_incomplete")
    supported["label"] = supported.label.astype(int)
    supported = supported.drop(columns="publisher_label")
    del raw, content
    novel, curation = curate_new(
        [supported],
        urls,
        domains,
        {
            "max_rows_per_domain": protocol["curation"]["max_rows_per_domain"],
            "split_salt": "v6-indonesia-external-20261106:",
            "group_buckets": {"new_test": 100},
        },
    )
    # Every new case is reserved. No new source enters training/calibration/selection.
    global_frame = novel.head(protocol["curation"]["global_max_rows"]).reset_index(
        drop=True
    )
    regional = novel.loc[structure_masks(novel)["id_suffix_proxy"]].reset_index(
        drop=True
    )
    overlap = len(
        set(global_frame.representation_digest) & set(regional.representation_digest)
    )
    verify_files({**bindings, **exposure, **identities})
    DATA.mkdir(parents=True)
    assets = {}
    for name, frame in {
        "supported": supported,
        "reserved": novel,
        "global": global_frame,
        "id_suffix_proxy": regional,
    }.items():
        path = DATA / (name + ".parquet")
        frame.to_parquet(path, index=False)
        assets[name] = {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": checksum(path),
            **coverage(frame),
        }
    sidecar = write_sidecar(SIDECAR, supported)
    frozen = {
        **started,
        "frozen_at_utc": now(),
        "source": protocol["source"],
        "prior_exposure_hashes": exposure,
        "actual_identity_hashes": identities,
        "intake": audit,
        "curation": curation,
        "assets": assets,
        "sidecar": sidecar,
        "global_and_regional_overlapping_rows": overlap,
        "model_predictions_performed": False,
        "human_gold": False,
        "indonesia_gold": False,
        "production_ready": False,
    }
    write_json(DATA / "frozen.json", frozen)
    write_json(
        ROOT / "ml/provenance/mendeley-vfs-indonesia-external-exposure.json",
        {
            "sidecar": sidecar,
            "intake_freeze_path": (DATA / "frozen.json").relative_to(ROOT).as_posix(),
            "intake_freeze_sha256": checksum(DATA / "frozen.json"),
            "scope": "all sanitized supported inputs, including excluded and all reserved test rows",
            "future_novelty_audits_must_include": True,
        },
    )
    print(
        json.dumps({"intake": audit, "curation": curation, "assets": assets}),
        flush=True,
    )


def check_freeze():
    frozen = read(DATA / "frozen.json")
    if (
        checksum(PROTOCOL) != frozen["protocol_sha256"]
        or checksum(AMENDMENT) != frozen["amendment_sha256"]
    ):
        raise ValueError("external_protocol_changed_after_intake")
    verify_files(
        {
            **frozen["source_hashes"],
            **frozen["prior_exposure_hashes"],
            **frozen["actual_identity_hashes"],
        }
    )
    verify_files(
        {
            item["path"]: item["sha256"]
            for item in [*frozen["assets"].values(), frozen["sidecar"]]
        }
    )
    for item in read(PROTOCOL)["models"].values():
        verify_files({item["artifact"]: item["sha256"]})
    return frozen


def evaluate():
    if REPORT.exists() or (RUN / "evaluation-started.json").exists():
        raise ValueError("external_final_test_already_started")
    frozen = check_freeze()
    protocol = read(PROTOCOL)
    write_json(
        RUN / "evaluation-started.json",
        {
            "started_at_utc": now(),
            "freeze_sha256": checksum(DATA / "frozen.json"),
            "models": protocol["models"],
        },
    )
    active = RichArtifact()
    if (
        active.metadata["thresholds"]["warning"]
        != protocol["models"]["active_v6"]["threshold"]
    ):
        raise ValueError("active_threshold_mismatch")
    research = joblib.load(
        ROOT / protocol["models"]["retained_weighted_research"]["artifact"]
    )
    cohorts, parity = {}, {}
    for name in ("global", "id_suffix_proxy"):
        frame = pd.read_parquet(ROOT / frozen["assets"][name]["path"])
        scores = {
            "active_v6": active.predict_cores(frame.core)
            if len(frame)
            else np.array([]),
            "retained_weighted_research": predict_bundle(research, frame.core)
            if len(frame)
            else np.array([]),
        }
        np.savez_compressed(RUN / (name + "-predictions.npz"), **scores)
        if len(frame):
            probe = frame.core.iloc[:128]
            replay = predict_bundle(
                joblib.load(
                    ROOT / protocol["models"]["retained_weighted_research"]["artifact"]
                ),
                probe,
            )
            delta = float(
                np.max(
                    np.abs(replay - scores["retained_weighted_research"][: len(probe)])
                )
            )
            active_delta = float(
                np.max(
                    np.abs(
                        RichArtifact().predict_cores(probe)
                        - scores["active_v6"][: len(probe)]
                    )
                )
            )
            if max(delta, active_delta) > 1e-12:
                raise ValueError("external_saved_model_prediction_parity_failed")
            parity[name] = {
                "rows": len(probe),
                "research_max_delta": delta,
                "active_max_delta": active_delta,
            }
        masks = {
            "all": np.ones(len(frame), dtype=bool),
            **{
                k: v.to_numpy()
                for k, v in structure_masks(frame).items()
                if k in protocol["subgroups"]
            },
        }
        results = {}
        for group, mask in masks.items():
            subset = frame.loc[mask]
            results[group] = {
                role: diagnostic_metrics(
                    subset,
                    values[mask],
                    protocol["models"][role]["threshold"],
                    protocol["bootstrap_repeats"],
                    protocol["seed"],
                )
                for role, values in scores.items()
            }
        paired = None
        if frame.label.eq(1).any():
            paired = paired_intervals(
                frame,
                scores["active_v6"],
                scores["retained_weighted_research"],
                [m["threshold"] for m in protocol["models"].values()],
                protocol["bootstrap_repeats"],
                protocol["seed"],
                frame.label.eq(1).all(),
            )
        cohorts[name] = {
            **coverage(frame),
            "results": results,
            "paired_research_minus_active": paired,
        }
        print("Evaluated " + name + ": " + str(len(frame)) + " rows", flush=True)
    check_freeze()
    report = {
        "completed_at_utc": now(),
        "protocol": protocol,
        "intake_freeze": frozen,
        "cohorts": cohorts,
        "saved_model_parity": parity,
        "human_validation": audit_human_inputs(ROOT / "ml/data/indonesia-gold/input"),
        "independent_indonesia_gold_evaluation_completed": False,
        "actual_model_fits": 0,
        "test_used_for_model_selection": False,
        "active_v6_unchanged": True,
        "production_ready": False,
    }
    write_json(REPORT, report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["intake", "evaluate", "verify"])
    args = parser.parse_args()
    with threadpool_limits(limits=4):
        {"intake": intake, "evaluate": evaluate, "verify": check_freeze}[args.stage]()


if __name__ == "__main__":
    main()
