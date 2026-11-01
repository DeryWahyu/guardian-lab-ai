"""Final evaluation of the already frozen winner; never fits a model."""

from __future__ import annotations

import json
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import psutil
from sklearn.metrics import precision_recall_curve
from threadpoolctl import threadpool_limits

from .evaluation import metrics, apply_calibration, group_bootstrap
from .metadata import checksum, dump_json, now
from .paths import DATA, REPORTS, ARTIFACTS
from .predictor import Predictor


def evaluate_subset(frame, probability, threshold):
    result = metrics(frame.label, probability, threshold)
    result["group_bootstrap"] = group_bootstrap(
        frame.label.to_numpy(),
        probability,
        frame.group.to_numpy(),
        threshold,
    )
    return result


def plot_evaluation(frame, probability, primary, validation):
    figure, axes = plt.subplots(1, 3, figsize=(14, 4.2), constrained_layout=True)
    precision, recall, _ = precision_recall_curve(frame.label, probability)
    axes[0].plot(recall, precision, color="#0f766e", lw=2)
    axes[0].set(
        xlabel="Recall",
        ylabel="Precision",
        title="New-domain temporal test",
        xlim=(0, 1),
        ylim=(0, 1.02),
    )
    bins = primary["reliability_bins"]
    axes[1].plot([0, 1], [0, 1], "--", color="#94a3b8")
    axes[1].plot(
        [item["mean_probability"] for item in bins],
        [item["phishing_fraction"] for item in bins],
        "o-",
        color="#0f766e",
    )
    axes[1].set(
        xlabel="Mean calibrated probability",
        ylabel="Observed phishing fraction",
        title="Calibration on research distribution",
        xlim=(0, 1),
        ylim=(0, 1),
    )
    candidates = validation["candidates"]
    axes[2].barh(
        [item["name"] for item in candidates],
        [item["tune"]["recall"] for item in candidates],
        color="#0f766e",
    )
    axes[2].set(
        xlabel="Recall at tune FPR <= 0.1%", title="Selection used validation only", xlim=(0, 1)
    )
    for ax in axes:
        ax.grid(alpha=0.2)
        ax.spines[["top", "right"]].set_visible(False)
    figure.savefig(REPORTS / "evaluation.png", dpi=180)
    figure.savefig(REPORTS / "evaluation.svg")
    plt.close(figure)


def main():
    frozen = json.loads((REPORTS / "frozen-selection.json").read_text())
    manifest = frozen["manifest"]
    assert checksum(DATA / "curated.parquet") == manifest["data_sha256"]
    assert checksum(ARTIFACTS / manifest["bundle_filename"]) == manifest["bundle_sha256"]
    start = time.perf_counter()
    predictor = Predictor()
    startup = time.perf_counter() - start
    bundle = predictor.bundle
    candidate = bundle["candidate"]
    frame = pd.read_parquet(DATA / "curated.parquet")
    features = pd.read_parquet(DATA / "features.parquet")
    threshold = manifest["thresholds"]["high"]
    outputs = {}
    for partition in ("test", "external"):
        mask = frame.partition == partition
        part = frame[mask].reset_index(drop=True)
        part_features = features[mask].reset_index(drop=True)
        raw = candidate.predict(part.core, part_features)
        probability = apply_calibration(bundle["calibrator"], raw)
        outputs[partition + "_all"] = evaluate_subset(part, probability, threshold)
        novel = part.novel_domain.to_numpy(dtype=bool)
        outputs[partition + "_novel_domain"] = evaluate_subset(
            part[novel], probability[novel], threshold
        )
        outputs[partition + "_by_risk_threshold"] = {
            name: metrics(part.label, probability, value)
            for name, value in manifest["thresholds"].items()
        }
        if partition == "test":
            for name, condition in {
                "hostname_id_suffix_not_proof_of_indonesia_targeting": part_features.suffix.eq(
                    "id"
                ).to_numpy(),
                "long_core_over_100_chars": part.core.str.len().gt(100).to_numpy(),
                "idn_punycode": part_features.punycode.eq(1).to_numpy(),
                "short_path": part_features.path_length.le(2).to_numpy(),
            }.items():
                if condition.sum() >= 20:
                    outputs["segment_" + name] = metrics(
                        part.label[condition], probability[condition], threshold
                    )
            plot_evaluation(
                part[novel],
                probability[novel],
                outputs["test_novel_domain"],
                json.loads((REPORTS / "validation-results.json").read_text()),
            )
            # Only aggregate suffix counts; no sample URLs or domain identities.
            mistakes = part_features[["suffix"]].copy()
            mistakes["fp"] = (part.label.to_numpy() == 0) & (probability >= threshold)
            mistakes["fn"] = (part.label.to_numpy() == 1) & (probability < threshold)
            grouped = mistakes.groupby("suffix")[["fp", "fn"]].sum()
            outputs["error_counts_by_suffix_min5"] = grouped[
                (grouped.fp + grouped.fn) >= 5
            ].to_dict("index")
    # Prediction parity is checked on in-memory synthetic inputs only.
    synthetic = "https://example.org/login?email=person%40example.net"
    direct = predictor.predict(synthetic, "URL")
    qr = predictor.predict(synthetic, "QR")
    assert direct["phishing_probability"] == qr["phishing_probability"]
    assert (
        direct["phishing_probability"]
        == predictor.predict("https://example.org/login")["phishing_probability"]
    )
    restored = Predictor()
    assert direct == restored.predict(synthetic)
    sample = frame[frame.partition == "test"].sample(100, random_state=20261101).core
    for core in sample.iloc[:5]:
        predictor.predict(core)
    elapsed = []
    for core in sample:
        start = time.perf_counter()
        predictor.predict(core)
        elapsed.append((time.perf_counter() - start) * 1000)
    info = psutil.Process().memory_info()._asdict()
    result = {
        "evaluated_at_utc": now(),
        "model_name": manifest["model_name"],
        "bundle_sha256": manifest["bundle_sha256"],
        "data_sha256": manifest["data_sha256"],
        "selection_frozen_before_final_test": True,
        "thresholds_frozen_before_final_test": True,
        "primary_evaluation": "test_novel_domain",
        "results": outputs,
        "inference_benchmark": {
            "samples": len(elapsed),
            "batch_size": 1,
            "threads": 4,
            "startup_seconds": startup,
            "latency_ms_p50": float(np.median(elapsed)),
            "latency_ms_p95": float(np.quantile(elapsed, 0.95)),
            "rss_bytes_evaluation_process_not_inference_only": info["rss"],
            "peak_working_set_bytes_if_available": info.get("peak_wset"),
        },
        "parity": {
            "url_equals_qr": True,
            "query_ignored_consistently": True,
            "save_reload_identical": True,
        },
        "limits": [
            "No manual re-verification of every source label; automated audits cannot prove all labels true.",
            "Domain-disjointness is not proof of campaign-disjointness.",
            "Independent Indonesia gold set and contemporary 2026 holdout remain unavailable.",
            "Research prevalence differs from live user traffic; precision and calibration will change.",
            "Query-only threats, redirect destinations, page content, and APK malware are outside this model.",
        ],
    }
    dump_json(REPORTS / "final-test.json", result)
    print(
        json.dumps(
            {"model": manifest["model_name"], "primary": outputs["test_novel_domain"]}, indent=2
        )
    )


if __name__ == "__main__":
    with threadpool_limits(limits=4):
        main()
