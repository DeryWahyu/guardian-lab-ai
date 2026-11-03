"""Replay frozen v6 quality checks without training or selecting thresholds."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import time
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve
from threadpoolctl import threadpool_limits

from guardian_ml.evaluation import metrics, wilson
from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.preprocessing import prepare_url
from guardian_ml.release_gates import assess_release
from guardian_ml.rich_artifact import RichArtifact
from guardian_ml.shadow_predictor import ShadowPredictor


def domain_intervals(data, scores, threshold, repeats, seed, positive_only=False):
    prediction = scores >= threshold
    labels = data.label.to_numpy()
    if positive_only and not np.all(labels == 1):
        raise ValueError("positive_only_requires_phishing_labels")
    counts = (
        pd.DataFrame(
            {
                "group": data.group.to_numpy(),
                "tn": (labels == 0) & ~prediction,
                "fp": (labels == 0) & prediction,
                "fn": (labels == 1) & ~prediction,
                "tp": (labels == 1) & prediction,
            }
        )
        .groupby("group", sort=True)
        .sum()
        .to_numpy(dtype=np.int64)
    )
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(repeats):
        tn, fp, fn, tp = counts[rng.integers(0, len(counts), len(counts))].sum(axis=0)
        if not (tp + fn) or (not positive_only and not (fp + tn)):
            continue
        draws.append(
            [tp / (tp + fn)]
            if positive_only
            else [tp / (tp + fn), fp / (fp + tn), tp / max(1, tp + fp)]
        )
    if not draws:
        raise ValueError("insufficient_domain_class_support")
    intervals = np.quantile(draws, [0.025, 0.975], axis=0)
    names = ["recall95"] if positive_only else ["recall95", "fpr95", "precision95"]
    return {
        "unit": "PSL registered domain/private hosting tenant",
        "repeats": repeats,
        "valid_repeats": len(draws),
        "discarded_class_absent_repeats": repeats - len(draws),
        "seed": seed,
        **{name: intervals[:, index].tolist() for index, name in enumerate(names)},
    }


def render_plot(path, vendor, scores, binary, positive, thresholds):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    warning = binary["warning"]
    counts = warning["confusion_matrix"]
    fig, axes = plt.subplots(2, 2, figsize=(13, 10), constrained_layout=True)
    ax = axes[0, 0]
    matrix = np.array([[counts["tn"], counts["fp"]], [counts["fn"], counts["tp"]]])
    ax.imshow(matrix, cmap="Blues")
    for (row, column), value in np.ndenumerate(matrix):
        ax.text(
            column,
            row,
            f"{value:,}",
            ha="center",
            va="center",
            fontsize=15,
            color="white" if value > matrix.max() / 2 else "black",
        )
    ax.set(
        xticks=[0, 1],
        yticks=[0, 1],
        xticklabels=["LOW", "MEDIUM / HIGH"],
        yticklabels=["Benign", "Phishing"],
        xlabel="Model output",
        ylabel="Source label",
        title="Vendor holdout: warning confusion counts",
    )
    ax = axes[0, 1]
    precision, recall, _ = precision_recall_curve(vendor.label, scores)
    ax.plot(
        recall,
        precision,
        color="#176b87",
        label=f"AP = {warning['average_precision']:.3f}",
    )
    for level, marker in [("warning", "o"), ("high", "s")]:
        result = binary[level]
        ax.scatter(
            result["recall"],
            result["precision"],
            s=65,
            marker=marker,
            label=f"Frozen {level}",
            zorder=4,
        )
    ax.axhline(
        float(vendor.label.mean()),
        linestyle="--",
        color="gray",
        label="Class prevalence",
    )
    ax.set(
        xlim=(0, 1),
        ylim=(0, 1.02),
        xlabel="Phishing recall",
        ylabel="Precision",
        title="Vendor precision-recall (diagnostic only)",
    )
    ax.legend(fontsize=8)
    ax = axes[1, 0]
    bins = warning["reliability_bins"]
    ax.plot([0, 1], [0, 1], "--", color="gray", label="Ideal calibration")
    ax.plot(
        [b["mean_probability"] for b in bins],
        [b["phishing_fraction"] for b in bins],
        "o-",
        color="#176b87",
        label="Observed vendor bins",
    )
    ax.set(
        xlim=(0, 1),
        ylim=(0, 1),
        xlabel="Mean model score",
        ylabel="Observed phishing fraction",
        title="Vendor calibration: research score is not traffic probability",
    )
    ax.legend(fontsize=8)
    ax = axes[1, 1]
    x = np.arange(2)
    for offset, results, label, color in [
        (-0.18, binary, "Vendor holdout", "#176b87"),
        (0.18, positive, "PhishTank positive only", "#db8f38"),
    ]:
        values = np.array([results[level]["recall"] for level in thresholds])
        intervals = np.array(
            [
                results[level]["recall_wilson95_rows_iid_assumption"]
                for level in thresholds
            ]
        )
        ax.bar(
            x + offset,
            100 * values,
            width=0.35,
            color=color,
            label=label,
            yerr=100 * np.stack([values - intervals[:, 0], intervals[:, 1] - values]),
            capsize=4,
        )
    ax.axhline(85, color="#a83a32", linestyle="--", label="Declared recall target")
    ax.set(
        xticks=x,
        xticklabels=list(thresholds),
        ylim=(0, 100),
        ylabel="Phishing recall (%)",
        title="Frozen policies; separate source distributions",
    )
    ax.legend(fontsize=8)
    fig.suptitle(
        "Frozen Logistic Regression v6 — replay of previously observed holdouts\n"
        "20,000 vendor URLs and 9,269 community positives; no training or threshold selection",
        fontsize=13,
    )
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol", type=Path, default=ROOT / "ml/reports/v6-quality-protocol.json"
    )
    parser.add_argument(
        "--output-stem", type=Path, default=ROOT / "ml/reports/v6-quality-evaluation"
    )
    parser.add_argument("--plot", action="store_true")
    args = parser.parse_args()
    args.protocol = args.protocol.resolve()
    args.output_stem = args.output_stem.resolve()
    if not args.output_stem.is_relative_to(ROOT):
        raise SystemExit("Evaluation output must stay inside this workspace")
    json_path = args.output_stem.with_suffix(".json")
    markdown_path = args.output_stem.with_suffix(".md")
    plot_path = args.output_stem.with_suffix(".png")
    if json_path.exists() or markdown_path.exists():
        raise SystemExit(
            "Choose a new --output-stem to preserve a completed evaluation"
        )
    started = time.perf_counter()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    original = json.loads((ROOT / "ml/reports/data-improvement-v6.json").read_text())
    artifact = RichArtifact()
    assert artifact.manifest["bundle_sha256"] == protocol["artifact_sha256"]
    assert (
        artifact.manifest["frozen_metadata_sha256"]
        == protocol["frozen_metadata_sha256"]
    )
    assert (
        checksum(ROOT / "ml/policies/shadow-runtime-manifest.json")
        == protocol["runtime_manifest_sha256"]
    )
    assert artifact.metadata["thresholds"] == protocol["thresholds"]
    print("Frozen artifact and protocol verified", flush=True)

    data_dir = ROOT / "ml/runs/notebook-tfidf-logistic-v6/data"
    data = {}
    for name, asset in protocol["datasets"].items():
        path = data_dir / asset["filename"]
        assert checksum(path) == asset["sha256"]
        frame = pd.read_parquet(path, columns=["core", "label", "group", "digest"])
        assert len(frame) == asset["rows"] and frame.digest.is_unique
        data[name] = frame
    vendor = data["new_deepurlbench_holdout"]
    feed = data["new_phishtank_positive"]
    assert set(vendor.label) == {0, 1} and set(feed.label) == {1}
    development_asset = original["data_manifest"]["outputs"]["development"]
    path = data_dir / development_asset["filename"]
    assert checksum(path) == development_asset["sha256"]
    development = pd.read_parquet(path, columns=["partition", "group", "digest"])
    assert development.groupby("group").partition.nunique().max() == 1
    for frame in (vendor, feed):
        assert not set(frame.group).intersection(development.group)
        assert not set(frame.digest).intersection(development.digest)
    assert not set(vendor.group).intersection(feed.group)
    assert not set(vendor.digest).intersection(feed.digest)
    del development
    print("Original caches and domain/digest separation verified", flush=True)

    reference = json.loads(
        (ROOT / "ml/provenance/v6-runtime-reference.json").read_text()
    )
    cores = [prepare_url(case["url"]).core for case in reference["cases"]]
    expected = np.array([case["probability"] for case in reference["cases"]])
    delta = float(np.max(np.abs(artifact.predict_cores(cores) - expected)))
    assert delta < reference["absolute_tolerance"]
    with threadpool_limits(limits=1):
        vendor_scores = artifact.predict_cores(vendor.core)
        feed_scores = artifact.predict_cores(feed.core)
    print(
        "Actual predictions completed for 29,269 previously observed URLs", flush=True
    )
    binary, positive = {}, {}
    bootstrap = protocol["domain_bootstrap"]
    for level, threshold in protocol["thresholds"].items():
        result = metrics(vendor.label, vendor_scores, threshold)
        result["balanced_accuracy"] = (result["recall"] + 1 - result["fpr"]) / 2
        result["groups"] = int(vendor.group.nunique())
        result["domain_bootstrap95"] = domain_intervals(
            vendor, vendor_scores, threshold, bootstrap["repeats"], bootstrap["seed"]
        )
        previous = original["binary_benchmarks"]["new_deepurlbench_domain_holdout"][
            "v6"
        ][level]
        assert result["confusion_matrix"] == previous["confusion_matrix"]
        binary[level] = result
        tp = int((feed_scores >= threshold).sum())
        previous = original["new_community_positive_sensitivity"]["v6"][level]
        assert tp == previous["tp"]
        positive[level] = {
            "rows": len(feed),
            "groups": int(feed.group.nunique()),
            "tp": tp,
            "fn": len(feed) - tp,
            "recall": tp / len(feed),
            "recall_wilson95_rows_iid_assumption": wilson(tp, len(feed)),
            "domain_bootstrap95": domain_intervals(
                feed,
                feed_scores,
                threshold,
                bootstrap["repeats"],
                bootstrap["seed"],
                positive_only=True,
            ),
            "accuracy": None,
            "precision": None,
            "fpr": None,
            "balanced_accuracy": None,
        }

    bins = binary["warning"]["reliability_bins"]
    ece = sum(
        b["rows"] * abs(b["mean_probability"] - b["phishing_fraction"]) for b in bins
    ) / len(vendor)
    predictor = ShadowPredictor(artifact)
    latency_spec = protocol["latency"]
    probes = vendor.core.sample(
        latency_spec["measured_requests"], random_state=latency_spec["random_seed"]
    ).tolist()
    timings = []
    with threadpool_limits(limits=latency_spec["threadpool_limit"]):
        for core in probes[: latency_spec["warmup_requests"]]:
            assert predictor.predict(core).status == "complete"
        for core in probes:
            tick = time.perf_counter_ns()
            reply = predictor.predict(core)
            timings.append((time.perf_counter_ns() - tick) / 1e6)
            assert reply.status == "complete"
    direct = predictor.predict("https://example.org/login", "URL")
    qr = predictor.predict("https://example.org/login", "QR")
    assert direct.model_score == qr.model_score
    invalid = predictor.predict("http://127.0.0.1/")
    assert invalid.model_score is None and invalid.risk_band is None
    private = predictor.predict("https://example.org/login?token=SYNTHETICPRIVATE")
    assert "SYNTHETICPRIVATE" not in private.model_dump_json()
    privacy_gap = (
        "SYNTHETICSHORT"
        in prepare_url("https://example.org/password=SYNTHETICSHORT").core
    )

    suite_path = ROOT / "ml/data/v6-quality-check/pytest-results.xml"
    tests = None
    if suite_path.exists():
        suites = list(ET.parse(suite_path).getroot().iter("testsuite"))
        tests = {
            key: sum(int(suite.attrib.get(key, 0)) for suite in suites)
            for key in ("tests", "failures", "errors", "skipped")
        }
        assert tests["failures"] == tests["errors"] == tests["skipped"] == 0
    assert (
        checksum(ROOT / artifact.manifest["artifact_path"])
        == protocol["artifact_sha256"]
    )
    assert (
        checksum(ROOT / artifact.manifest["frozen_metadata_path"])
        == protocol["frozen_metadata_sha256"]
    )
    report = {
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": protocol["scope"],
        "new_independent_test": False,
        "training_performed": False,
        "thresholds_changed": False,
        "artifact_sha256": protocol["artifact_sha256"],
        "frozen_metadata_sha256": protocol["frozen_metadata_sha256"],
        "runtime_manifest_sha256": protocol["runtime_manifest_sha256"],
        "protocol_sha256": checksum(args.protocol),
        "evaluation_script_sha256": checksum(__file__),
        "thresholds": protocol["thresholds"],
        "python_tests": tests,
        "integrity": {
            "original_binary_and_metadata_unchanged": True,
            "caches_match_original_hashes": True,
            "domain_and_digest_disjoint_from_development": True,
            "synthetic_reference_cases": len(cores),
            "maximum_reference_probability_error": delta,
            "original_confusion_counts_reproduced": True,
            "url_qr_parity": True,
            "unsupported_input_has_no_score_or_band": True,
            "response_does_not_echo_target": True,
        },
        "vendor_holdout": binary,
        "community_positive_only": positive,
        "vendor_constant_benign_reference": {
            "accuracy": float(vendor.label.eq(0).mean()),
            "balanced_accuracy": 0.5,
            "recall": 0.0,
            "role": "class_imbalance_reference_not_a_trained_or_selected_model",
        },
        "vendor_calibration": {
            "mean_model_score": float(vendor_scores.mean()),
            "source_labeled_phishing_fraction": float(vendor.label.mean()),
            "ece_10_fixed_bins": float(ece),
            "recalibration_performed": False,
        },
        "local_warm_latency_ms": {
            "requests": len(timings),
            "p50": float(np.quantile(timings, 0.5)),
            "p95": float(np.quantile(timings, 0.95)),
            "p99": float(np.quantile(timings, 0.99)),
            "scope": latency_spec["interpretation"],
            "threadpool_limit": latency_spec["threadpool_limit"],
            "platform": platform.system(),
            "python": platform.python_version(),
        },
        "release_gate": assess_release(),
        "known_limitations": [
            *protocol["limitations"],
            "Domain bootstrap does not establish campaign independence or label correctness.",
            "The frozen path sanitizer retains some short secrets in path assignments.",
        ],
        "known_path_redaction_gap_reproduced_with_synthetic_input": privacy_gap,
        "verdict": "not_sufficiently_reliable_as_a_standalone_public_phishing_detector",
        "production_ready": False,
        "elapsed_seconds": time.perf_counter() - started,
    }
    args.output_stem.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_bytes(
        (json.dumps(report, indent=2, allow_nan=False) + "\n").encode()
    )
    if args.plot:
        render_plot(
            plot_path, vendor, vendor_scores, binary, positive, protocol["thresholds"]
        )
    warning, high = binary["warning"], binary["high"]
    counts = warning["confusion_matrix"]
    text = f"""# Pengujian Kualitas Frozen v6

Kesimpulan: v6 belum cukup andal sebagai satu-satunya pendeteksi phishing untuk penggunaan publik. Implementasi berjalan konsisten, tetapi recall masih rendah dan release gate belum terpenuhi.

Pengujian ini memprediksi ulang 29.269 URL yang sebelumnya sudah teramati: 20.000 URL vendor dua kelas dan 9.269 phishing komunitas. Ini bukan holdout independen baru. Binary, metadata dan threshold asli tetap sama; tidak ada training, relabel, pemilihan threshold atau pengambilan URL baru.

| Pengujian | Accuracy | Precision | Recall phishing | FPR |
| --- | ---: | ---: | ---: | ---: |
| Vendor, warning MEDIUM+HIGH | {100 * warning["accuracy"]:.2f}% | {100 * warning["precision"]:.2f}% | {100 * warning["recall"]:.2f}% | {100 * warning["fpr"]:.3f}% |
| Vendor, HIGH saja | {100 * high["accuracy"]:.2f}% | {100 * high["precision"]:.2f}% | {100 * high["recall"]:.2f}% | {100 * high["fpr"]:.3f}% |
| PhishTank, warning | Tidak tersedia | Tidak tersedia | {100 * positive["warning"]["recall"]:.2f}% | Tidak tersedia |
| PhishTank, HIGH | Tidak tersedia | Tidak tersedia | {100 * positive["high"]["recall"]:.2f}% | Tidak tersedia |

## Arti hasil

Pada vendor, {counts["tp"]:,} dari {warning["phishing"]:,} phishing tertangkap; {counts["fn"]:,} terlewat. Dari {warning["benign"]:,} benign, {counts["fp"]:,} salah mendapat warning. Pada PhishTank, {positive["warning"]["tp"]:,} tertangkap dan {positive["warning"]["fn"]:,} terlewat. Distribusi feed positif dan benign historis berbeda; jangan menggabungkannya sebagai accuracy atau precision trafik.

Accuracy vendor {100 * warning["accuracy"]:.2f}% perlu dibaca bersama balanced accuracy {100 * warning["balanced_accuracy"]:.2f}%. Referensi konstan yang selalu menyebut benign mendapat accuracy {100 * report["vendor_constant_benign_reference"]["accuracy"]:.2f}% namun recall nol; ini hanya pembanding ketimpangan kelas, bukan model alternatif.

Wilson 95% recall vendor sekitar [{100 * warning["recall_wilson95_rows_iid_assumption"][0]:.2f}%; {100 * warning["recall_wilson95_rows_iid_assumption"][1]:.2f}%]. Wilson FPR sekitar [{100 * warning["fpr_wilson95_rows_iid_assumption"][0]:.3f}%; {100 * warning["fpr_wilson95_rows_iid_assumption"][1]:.3f}%], sehingga bukti belum mendukung jaminan FPR di bawah 1%. Bootstrap domain 1.000 kali dan semua interval tersimpan dalam JSON. Interval tidak menghapus ketidakpastian label atau campaign overlap.

ROC-AUC vendor {warning["roc_auc"]:.4f}, AP {warning["average_precision"]:.4f}, Brier {warning["brier_score"]:.5f}. Mean model score {report["vendor_calibration"]["mean_model_score"]:.4f} dibanding fraksi phishing berlabel sumber {report["vendor_calibration"]["source_labeled_phishing_fraction"]:.4f}; skor riset tidak otomatis menjadi probabilitas trafik. Tidak ada kalibrasi ulang pada holdout.

## Implementasi dan runtime

Tes Python: {tests["tests"] if tests else "tidak disediakan"} lulus tanpa failure/error/skip. Checksum, domain/digest separation, 62 referensi sintetis dan prediksi URL/QR cocok. Input unsupported tanpa skor/band dan respons tidak menggemakan target. Gap redaksi path pendek tetap direproduksi dengan input sintetis; parser beku tidak diubah.

Probe warm 128 request berurutan pada satu proses lokal: p50 {report["local_warm_latency_ms"]["p50"]:.2f} ms, p95 {report["local_warm_latency_ms"]["p95"]:.2f} ms. Termasuk parser, fitur, classifier, kalibrator dan respons shadow; tidak mencakup HTTP/jaringan/cold start atau beban deployment.

## Penggunaan yang didukung bukti

Gunakan untuk prototipe atau riset/internal shadow dengan verifikasi lanjutan. Gold Indonesia dan benign kontemporer belum tersedia, sebagian label masih memerlukan review, dan target lower-bound recall 85% belum tercapai. LOW bukan SAFE. Memakai hanya HIGH menurunkan cakupan deteksi lebih jauh.

Laporan angka: [{json_path.name}]({json_path.name}). Protokol sebelum scoring: [v6-quality-protocol.json](v6-quality-protocol.json). Replay ini tidak mengubah bobot/threshold atau status produksi.
"""
    if args.plot:
        text += f"\n![Ringkasan evaluasi v6]({plot_path.name})\n"
    markdown_path.write_bytes(text.encode())
    print(
        json.dumps(
            {
                "report": str(json_path.relative_to(ROOT)),
                "markdown": str(markdown_path.relative_to(ROOT)),
                "vendor_accuracy": warning["accuracy"],
                "vendor_recall": warning["recall"],
                "vendor_fpr": warning["fpr"],
                "community_recall": positive["warning"]["recall"],
                "production_ready": False,
            }
        )
    )


if __name__ == "__main__":
    main()
