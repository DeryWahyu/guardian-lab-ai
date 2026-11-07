"""Audit frozen v6 errors, label ambiguity and development threshold trade-offs."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.special import logit
from threadpoolctl import threadpool_limits

from guardian_ml.features import KEYWORDS
from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.preprocessing import EXTRACT, prepare_url
from guardian_ml.rich_artifact import RichArtifact
from guardian_ml.rich_features import feature_matrix

from experiment_v6_development import paired_intervals
from evaluate_v6_quality import domain_intervals
from v6_development_support import predict_bundle
from v6_diagnostic_support import (
    export_review_queues,
    indonesia_inventory,
    label_conflict_audit,
    safe_metrics,
    threshold_diagnostics,
)
from validate_v6 import validate

CACHE = ROOT / "ml/runs/notebook-tfidf-logistic-v6/data"
SOURCE_FILES = [
    "scripts/evaluate_v6_diagnostics.py",
    "scripts/v6_diagnostic_support.py",
    "scripts/v6_development_support.py",
    "scripts/experiment_v6_development.py",
    "scripts/validate_v6.py",
]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2, allow_nan=False) + "\n").encode())


def load_cache(asset):
    path = CACHE / asset["filename"]
    if checksum(path) != asset["sha256"]:
        raise ValueError("diagnostic_cache_checksum_mismatch")
    frame = pd.read_parquet(path)
    if len(frame) != asset["rows"]:
        raise ValueError("diagnostic_cache_row_mismatch")
    return frame


def scores_and_flags(artifact, frame, include_flags=True):
    encoder = artifact.bundle["encoder"]
    scores, char_empty, word_empty = [], [], []
    char_end = len(encoder["char"].vocabulary_)
    word_end = char_end + len(encoder["word"].vocabulary_)
    for start in range(0, len(frame), 4096):
        batch = frame.core.iloc[start : start + 4096]
        matrix = feature_matrix(encoder, batch)
        raw = artifact.bundle["classifier"].predict_proba(matrix)[:, 1]
        scores.extend(
            artifact.bundle["calibrator"].predict_proba(
                logit(np.clip(raw, 1e-7, 1 - 1e-7)).reshape(-1, 1)
            )[:, 1]
        )
        if include_flags:
            char_empty.extend(matrix[:, :char_end].getnnz(axis=1) == 0)
            word_empty.extend(matrix[:, char_end:word_end].getnnz(axis=1) == 0)
    scores = np.asarray(scores)
    if len(frame):
        count = min(32, len(frame))
        if not np.allclose(
            scores[:count],
            artifact.predict_cores(frame.core.iloc[:count]),
            rtol=0,
            atol=1e-12,
        ):
            raise ValueError("diagnostic_scoring_saved_artifact_parity_failed")
    if not include_flags:
        return scores, None
    flags = []
    for core, char_missing, word_missing in zip(frame.core, char_empty, word_empty):
        parsed = prepare_url(core)
        text = core.split("://", 1)[1]
        flags.append(
            {
                "length": len(text),
                "long_url": len(text) > 120,
                "private_hosting": bool(EXTRACT(parsed.host).is_private),
                "punycode": "xn--" in parsed.host,
                "root_path": parsed.path == "/",
                "keyword_present": any(word in text.lower() for word in KEYWORDS),
                "redaction_placeholder": "REDACTED" in parsed.path,
                "word_vector_empty": bool(word_missing),
                "char_vector_empty": bool(char_missing),
                "suffix_id": parsed.host.endswith(".id"),
            }
        )
    return scores, pd.DataFrame(flags, index=frame.index)


def error_audit(frame, flags, scores, threshold, protocol, positive_only=False):
    overall = safe_metrics(frame, scores, threshold, positive_only)
    total_fn = overall["confusion_matrix"]["fn"]
    segments = {}

    def record(name, mask):
        result = safe_metrics(
            frame.loc[mask], scores[np.asarray(mask)], threshold, positive_only
        )
        result["share_of_all_false_negatives"] = (
            result["confusion_matrix"]["fn"] / total_fn if total_fn else None
        )
        segments[name] = result

    for name in protocol["segment_flags"]:
        for value in (True, False):
            record(name + ("_yes" if value else "_no"), flags[name].eq(value))
    lower = -1
    for upper in [*protocol["length_bins"], np.inf]:
        name = f"length_{lower + 1}_{int(upper) if np.isfinite(upper) else 'plus'}"
        record(name, flags.length.gt(lower) & flags.length.le(upper))
        lower = upper
    for index, (lower, upper) in enumerate(
        zip(protocol["score_bins"], protocol["score_bins"][1:])
    ):
        record(f"score_bin_{index}", (scores >= lower) & (scores < upper))
    sources = {}
    if "training_source" in frame:
        for source in sorted(frame.training_source.unique()):
            mask = frame.training_source.eq(source)
            sources[source] = safe_metrics(
                frame.loc[mask], scores[mask.to_numpy()], threshold
            )
    return {
        "overall": overall,
        "segments": segments,
        "source_metrics": sources,
        "interpretation": "overlapping descriptive associations; no causal error labels or verified Indonesian relevance",
    }


def paired_segment_audit(
    frame, flags, scores, candidate_scores, thresholds, protocol, positive_only
):
    output = {}
    for name in ("private_hosting", "long_url", "punycode"):
        mask = flags[name].to_numpy()
        selected = frame.loc[mask]
        if selected.empty:
            output[name] = None
            continue
        entry = {
            "v6": safe_metrics(selected, scores[mask], thresholds[0], positive_only),
            "candidate": safe_metrics(
                selected, candidate_scores[mask], thresholds[1], positive_only
            ),
        }
        if positive_only or set(selected.label) == {0, 1}:
            entry["paired_domain_delta95"] = paired_intervals(
                selected,
                scores[mask],
                candidate_scores[mask],
                thresholds,
                protocol["domain_bootstrap_repeats"],
                protocol["seed"],
                positive_only,
            )
        output[name] = entry
    return output


def date_inventory(development):
    result = {}
    for source, subset in development.groupby("training_source", sort=True):
        rows = {}
        for label in (0, 1):
            dates = pd.to_datetime(
                subset.loc[subset.label.eq(label), "date"], errors="coerce", utc=True
            )
            rows[str(label)] = {
                "rows": len(dates),
                "dated_rows": int(dates.notna().sum()),
                "min": None if not dates.notna().any() else dates.min().isoformat(),
                "max": None if not dates.notna().any() else dates.max().isoformat(),
            }
        result[source] = rows
    return {
        "sources": result,
        "meaning": "publisher/cache date fields, not fresh verification or proof of benign status",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "ml/reports/v6-diagnostic-evaluation-protocol.json",
    )
    parser.add_argument(
        "--output-stem", type=Path, default=ROOT / "ml/reports/v6-diagnostic-evaluation"
    )
    parser.add_argument(
        "--review-dir", type=Path, default=ROOT / "ml/data/v6-diagnostic-evaluation"
    )
    args = parser.parse_args()
    output, review_dir = args.output_stem.resolve(), args.review_dir.resolve()
    if not output.is_relative_to(ROOT / "ml/reports") or not review_dir.is_relative_to(
        ROOT / "ml/data"
    ):
        raise ValueError("diagnostic_output_outside_allowed_directories")
    if (
        any(output.with_suffix(suffix).exists() for suffix in (".json", ".md", ".png"))
        or review_dir.exists()
    ):
        raise ValueError("diagnostic_output_already_exists_choose_new_paths")
    protocol = json.loads(args.protocol.read_text())
    original_protocol = json.loads(
        (ROOT / protocol["development_protocol"]).read_text()
    )
    artifact = RichArtifact()
    registry = ROOT / "ml/data/indonesia-gold/registry/known-exposure.sqlite"
    registry_hash = checksum(registry)
    sources = {name: checksum(ROOT / name) for name in SOURCE_FILES}
    protocol_hash = checksum(args.protocol)
    write_json(
        output.with_suffix(".started.json"),
        {
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "protocol_sha256": protocol_hash,
            "source_hashes": sources,
            "registry_sha256": registry_hash,
        },
    )
    integrity = validate()
    development = load_cache(original_protocol["development"])
    if development.groupby("group").partition.nunique().max() != 1:
        raise ValueError("development_group_leakage")
    conflicts, coordinator, blind = label_conflict_audit(development)
    export_review_queues(review_dir, coordinator, blind)
    print("Conflict audit complete; hash-only review queues saved locally", flush=True)
    inventory = indonesia_inventory(ROOT / "ml/data/indonesia-gold")
    dates = date_inventory(development)
    audit, segment_changes = {}, {}
    with threadpool_limits(limits=4):
        tune = development.loc[development.partition.eq("tune")].reset_index(drop=True)
        tune_scores, flags = scores_and_flags(artifact, tune)
        audit["tune"] = error_audit(
            tune,
            flags,
            tune_scores,
            artifact.metadata["thresholds"]["warning"],
            protocol,
        )
        print("Development tune error audit complete", flush=True)
        threshold_frame = development.loc[
            development.partition.eq("threshold")
        ].reset_index(drop=True)
        threshold_scores, _ = scores_and_flags(artifact, threshold_frame, False)
        tradeoffs = threshold_diagnostics(
            threshold_frame,
            threshold_scores,
            tune,
            tune_scores,
            protocol["diagnostic_fpr_budgets_per_source"],
        )
        for policy in tradeoffs:
            policy["tune"]["domain_bootstrap95"] = domain_intervals(
                tune,
                tune_scores,
                policy["threshold"],
                protocol["domain_bootstrap_repeats"],
                protocol["seed"],
            )
        print(
            "Five threshold policies evaluated on tune only; serving policy unchanged",
            flush=True,
        )
        candidate_freeze = json.loads((ROOT / protocol["candidate_freeze"]).read_text())
        if (
            checksum(ROOT / protocol["candidate_artifact"])
            != candidate_freeze["selected_bundle_sha256"]
        ):
            raise ValueError("diagnostic_candidate_checksum_mismatch")
        for name, expected in candidate_freeze["source_hashes"].items():
            if checksum(ROOT / name) != expected:
                raise ValueError("diagnostic_candidate_source_changed")
        candidate = joblib.load(ROOT / protocol["candidate_artifact"])
        previous = json.loads((ROOT / protocol["candidate_report"]).read_text())
        seen_groups, seen_digests = set(development.group), set(development.digest)
        for name, asset in original_protocol["benchmarks"].items():
            frame = load_cache(asset).reset_index(drop=True)
            if seen_groups.intersection(frame.group) or seen_digests.intersection(
                frame.digest
            ):
                raise ValueError("benchmark_identity_overlap")
            seen_groups.update(frame.group)
            seen_digests.update(frame.digest)
            scores, flags = scores_and_flags(artifact, frame)
            positive_only = name == "community_positive"
            audit[name] = error_audit(
                frame,
                flags,
                scores,
                artifact.metadata["thresholds"]["warning"],
                protocol,
                positive_only,
            )
            new_scores = predict_bundle(candidate, frame.core)
            threshold = candidate["metadata"]["thresholds"]["warning"]
            compared = safe_metrics(frame, new_scores, threshold, positive_only)
            expected = previous["benchmarks"][name]["models"]["candidate"]["warning"]
            if positive_only:
                if compared["confusion_matrix"]["tp"] != expected["tp"]:
                    raise ValueError("candidate_positive_counts_changed")
            elif compared["confusion_matrix"] != expected["confusion_matrix"]:
                raise ValueError("candidate_binary_counts_changed")
            segment_changes[name] = paired_segment_audit(
                frame,
                flags,
                scores,
                new_scores,
                [artifact.metadata["thresholds"]["warning"], threshold],
                protocol,
                positive_only,
            )
            print(
                "Observed benchmark errors and paired segment audit complete: " + name,
                flush=True,
            )
    if checksum(registry) != registry_hash or sources != {
        name: checksum(ROOT / name) for name in SOURCE_FILES
    }:
        raise ValueError("diagnostic_source_or_exposure_registry_changed")
    final_integrity = validate()
    if final_integrity["artifact_sha256"] != integrity["artifact_sha256"]:
        raise ValueError("diagnostic_frozen_model_changed")
    report = {
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": protocol_hash,
        "source_hashes": sources,
        "runtime_integrity": final_integrity,
        "exposure_registry_unchanged": True,
        "new_independent_test": False,
        "production_ready": False,
        "training_performed": False,
        "serving_thresholds_changed": False,
        "label_conflicts": conflicts,
        "error_audits": audit,
        "paired_segment_regressions": segment_changes,
        "development_threshold_tradeoffs": tradeoffs,
        "indonesia_readiness": inventory,
        "development_date_inventory": dates,
        "blind_review_rows": len(blind),
        "human_label_verification": "pending_real_independent_reviews",
        "limitations": protocol["limitations"],
    }
    write_json(output.with_suffix(".json"), report)
    render_report(output.with_suffix(".md"), report, review_dir)
    render_plot(output.with_suffix(".png"), report)
    print(
        "Diagnostic report and plot saved; human-review tasks remain explicit",
        flush=True,
    )


def render_report(path, report, review_dir):
    conflicts = report["label_conflicts"]
    lines = [
        "# Evaluasi lanjutan frozen v6",
        "",
        "Audit otomatis selesai untuk kesalahan, konflik representasi/label, hasil per kelompok dan trade-off threshold development. Verifikasi kebenaran label oleh manusia serta pengujian Indonesia independen masih menunggu kandidat dan hasil review nyata.",
        "",
        "Tidak ada training atau perubahan threshold layanan. Semua cohort sudah pernah terpapar. Angka di bawah mengikuti label sumber, bukan penetapan label baru.",
        "",
        "## Kesalahan pada threshold warning asli",
        "",
        "| Cohort | URL | TP | FN | FP | Precision | Recall | FPR |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    def percent(value):
        return "N/A" if value is None else f"{value:.3%}"

    for name, audit in report["error_audits"].items():
        row = audit["overall"]
        count = row["confusion_matrix"]
        fp = "N/A" if name == "community_positive" else str(count["fp"])
        lines.append(
            f"| {name} | {row['rows']:,} | {count['tp']} | {count['fn']} | {fp} | {percent(row['precision'])} | {percent(row['recall'])} | {percent(row['fpr'])} |"
        )
    lines += [
        "",
        "## Pola false negative",
        "",
        "Kelompok saling tumpang tindih. Share FN adalah proporsi seluruh phishing terlewat dalam cohort, bukan estimasi penyebab atau kepastian label. Perbandingan berikut bersifat eksplorasi setelah melihat eksperimen.",
        "",
        "| Cohort | Kelompok | URL | Phishing | FN | Share seluruh FN | Recall | FPR |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, audit in report["error_audits"].items():
        for segment in (
            "root_path_yes",
            "root_path_no",
            "private_hosting_yes",
            "private_hosting_no",
            "long_url_yes",
            "word_vector_empty_yes",
            "char_vector_empty_yes",
            "keyword_present_no",
        ):
            row = audit["segments"][segment]
            lines.append(
                f"| {name} | {segment} | {row['rows']} | {row['phishing']} | {row['confusion_matrix']['fn']} | {percent(row['share_of_all_false_negatives'])} | {percent(row['recall'])} | {percent(row['fpr'])} |"
            )
    lines += [
        "",
        "Host/path, panjang, keyword, redaksi, vocabulary coverage dan `.id` hanya indikator struktur. Tidak ada inspeksi halaman atau bukti bahwa URL tertentu menargetkan Indonesia. Query/fragment asli sudah dibuang dan tidak dapat dipakai menjelaskan penyebab error.",
        "",
        "## Konflik label",
        "",
        f"Ada {conflicts['conflicting_representations']} representasi development dengan label bertentangan ({conflicts['conflicting_rows']} baris); distribusi per partisi: `{json.dumps(conflicts['partition_representations'], sort_keys=True)}`. Konflik fit adalah subset yang dikarantina pada eksperimen sebelumnya.",
        "",
        f"Lintas sumber: {conflicts['cross_source_representations']}; konflik dalam sumber: {conflicts['within_source_representations']}; core cache identik dengan label berbeda: {conflicts['exact_cached_core_conflicts']}; memuat placeholder redaksi: {conflicts['with_redaction_placeholder']}; lebih dari satu tanggal diketahui: {conflicts['with_multiple_known_dates']}.",
        "",
        f"Dua antrean review blind dan satu daftar koordinator disimpan hanya lokal di `{review_dir.relative_to(ROOT).as_posix()}`. Berisi locator hash cache tanpa URL target; label sumber dan prediksi tidak masuk antrean blind. Reviewer harus menggunakan bukti penerbit, mengisi label/uncertain/out_of_scope dan evidence_ref. Tidak ada label yang diubah atau reviewer yang dibuat otomatis.",
        "",
        "## Perbandingan kelompok kandidat terhadap v6",
        "",
    ]
    for dataset, segments in report["paired_segment_regressions"].items():
        for name, item in segments.items():
            if item is None:
                continue
            old, new = item["v6"], item["candidate"]
            interval = item.get("paired_domain_delta95", {})
            delta = interval.get("recall_delta95")
            formatted = (
                None if delta is None else [round(100 * value, 3) for value in delta]
            )
            lines.append(
                f"- {dataset}, {name}: recall {percent(old['recall'])} menjadi {percent(new['recall'])}; FPR {percent(old['fpr'])} menjadi {percent(new['fpr'])}; 95% domain-bootstrap delta recall (percentage point) {formatted}."
            )
    lines += [
        "",
        "## Threshold development",
        "",
        "Setiap threshold dipilih hanya pada partisi threshold, kemudian dinilai pada tune yang terpisah domain/digest. Lima budget ditentukan sebelum scoring audit. Semua merupakan diagnostik; tidak ada policy yang dipilih untuk layanan atau dioptimalkan pada benchmark.",
        "",
        "| Budget FPR per sumber, threshold partition | Threshold | Recall tune | FPR tune | Precision tune | FP tune | FN tune |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for policy in report["development_threshold_tradeoffs"]:
        row = policy["tune"]
        lines.append(
            f"| {policy['budget']:.1%} | {policy['threshold']:.9f} | {percent(row['recall'])} | {percent(row['fpr'])} | {percent(row['precision'])} | {row['confusion_matrix']['fp']} | {row['confusion_matrix']['fn']} |"
        )
    lines += [
        "",
        "FPR empiris partisi threshold tidak menjamin FPR di tune, sumber lain atau populasi. Skor/kalibrasi tetap mengacu pada campuran riset, bukan probabilitas trafik Indonesia. Counts, source rates, Wilson dan calibration bins tersedia dalam JSON.",
        "",
        "## Kesiapan validasi Indonesia",
        "",
        f"Input aktual: `{json.dumps(report['indonesia_readiness']['actual_input_rows'], sort_keys=True)}`. Belum ada holdout Indonesia dengan label dan identitas reviewer independen yang terverifikasi; metrik Indonesia tidak dihitung.",
        "",
        "Rencana pengumpulan dan pembekuan ada di `ai-agent-docs/v6-indonesia-validation-readiness.md`. Minimum 1.000 phishing/3.000 benign dan dua reviewer adalah syarat awal, bukan bukti otomatis lolos. Pilot lama yang sudah terpapar tidak menjadi holdout baru.",
        "",
        "## Reproduksi dan batas bukti",
        "",
        "```powershell",
        "ml/.venv/Scripts/python.exe scripts/evaluate_v6_diagnostics.py --output-stem ml/reports/v6-diagnostic-replay --review-dir ml/data/v6-diagnostic-replay",
        "```",
        "",
        "Memerlukan extra `quality`, cache v6 lokal dan kandidat eksperimen yang checksum/source-nya cocok. Output lengkap bersifat agregat; dataset/review queues tetap diabaikan Git. Guard runtime, 62 referensi sintetis dan registry exposure diperiksa sebelum/sesudah audit.",
        "",
    ]
    lines += ["- " + item for item in report["limitations"]]
    path.write_bytes(("\n".join(lines) + "\n").encode())


def render_plot(path, report):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    policies = report["development_threshold_tradeoffs"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)
    recall = [100 * point["tune"]["recall"] for point in policies]
    fpr = [100 * point["tune"]["fpr"] for point in policies]
    axes[0].plot(fpr, recall, "o-", color="#176b87")
    for policy, x, y in zip(policies, fpr, recall):
        axes[0].annotate(
            f"budget {policy['budget']:.1%}",
            (x, y),
            xytext=(5, 4),
            textcoords="offset points",
            fontsize=8,
        )
    axes[0].set(
        xlabel="Observed tune FPR (%)",
        ylabel="Tune phishing recall (%)",
        title="Threshold selected on separate threshold partition",
    )
    axes[0].axhline(85, color="#a83a32", linestyle="--", label="Recall target")
    axes[0].set_ylim(0, 100)
    axes[0].legend(fontsize=8)
    vendor = report["error_audits"]["vendor"]["segments"]
    names = [
        "root_path_yes",
        "root_path_no",
        "private_hosting_yes",
        "private_hosting_no",
    ]
    values = [vendor[name]["recall"] * 100 for name in names]
    axes[1].barh(range(len(names)), values, color="#db8f38")
    axes[1].set(
        yticks=range(len(names)),
        yticklabels=["Root path", "Non-root path", "Private hosting", "Other hosting"],
        xlim=(0, 100),
        xlabel="Vendor phishing recall (%)",
        title="Frozen warning; overlapping descriptive segments",
    )
    for index, value in enumerate(values):
        axes[1].text(value + 1, index, f"{value:.1f}%", va="center", fontsize=9)
    fig.suptitle(
        "Frozen v6 diagnostic audit — previously observed data\nNo training or serving threshold changes; Indonesia human validation pending"
    )
    fig.savefig(path, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
