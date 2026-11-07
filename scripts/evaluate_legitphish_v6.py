"""Pinned, memory-only public intake and frozen-v6 evaluation of LegitPhish V2."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sqlite3
from urllib.parse import urljoin, urlsplit

import pandas as pd
import requests
from threadpoolctl import threadpool_limits

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from guardian_ml.preprocessing import EXTRACT, InvalidUrl, prepare_url
from guardian_ml.rich_artifact import RichArtifact

from evaluate_v6_quality import domain_intervals
from v6_development_support import prepare_experiment_url, representation_digest
from v6_diagnostic_support import safe_metrics
from validate_v6 import validate

PROTOCOL = ROOT / "ml/reports/legitphish-v6-protocol-amended.json"
SOURCES = [
    "scripts/evaluate_legitphish_v6.py",
    "scripts/v6_diagnostic_support.py",
    "scripts/v6_development_support.py",
    "scripts/evaluate_v6_quality.py",
]


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2, allow_nan=False) + "\n").encode())


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def download_bytes(asset):
    """Only the pinned repository asset, never any target contained in the CSV."""
    url = asset["download_url"]
    for _ in range(5):
        host = urlsplit(url).hostname or ""
        if urlsplit(url).scheme != "https" or not (
            host == "data.mendeley.com"
            or (".s3" in host and host.endswith(".amazonaws.com"))
        ):
            raise ValueError("unapproved_dataset_download_host")
        with requests.get(
            url,
            stream=True,
            allow_redirects=False,
            timeout=(15, 45),
            headers={"User-Agent": "GuardianLabAI-research-dataset-audit/1.0"},
        ) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                url = urljoin(url, response.headers["Location"])
                continue
            response.raise_for_status()
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > asset["bytes"]:
                    raise ValueError("dataset_download_exceeds_pinned_size")
        if (
            len(content) != asset["bytes"]
            or hashlib.sha256(content).hexdigest() != asset["sha256"]
        ):
            raise ValueError("dataset_download_integrity_mismatch")
        return bytes(content)
    raise ValueError("too_many_dataset_redirects")


def read_release(content):
    frame = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
    if "URL" not in frame or "ClassLabel" not in frame:
        raise ValueError("unexpected_legitphish_url_or_label_schema")
    labels = pd.to_numeric(frame.ClassLabel, errors="coerce")
    if (labels.isna() & frame.ClassLabel.notna()).any() or not labels.dropna().isin(
        [0, 1]
    ).all():
        raise ValueError("unknown_legitphish_publisher_labels")
    valid = labels.notna()
    result = pd.DataFrame(
        {"url": frame.loc[valid, "URL"], "label": (1 - labels[valid]).astype(int)}
    )
    counts = {str(int(k)): int(v) for k, v in labels.value_counts().items()}
    if not valid.all():
        counts["missing_label_quarantined"] = int((~valid).sum())
    return (
        result,
        list(frame.columns),
        counts,
    )


def inspect_labels(asset):
    content = download_bytes(asset)
    frame = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
    labels = pd.to_numeric(frame["ClassLabel"], errors="coerce")
    report = {
        "asset_sha256": asset["sha256"],
        "raw_rows": len(frame),
        "columns": list(frame.columns),
        "numeric_label_counts": {
            str(float(k)): int(v) for k, v in labels.dropna().value_counts().items()
        },
        "missing_label_rows": int(frame.ClassLabel.isna().sum()),
        "nonnumeric_nonmissing_label_rows": int(
            (labels.isna() & frame.ClassLabel.notna()).sum()
        ),
        "entirely_empty_rows": int(frame.isna().all(axis=1).sum()),
        "missing_url_rows": int(frame.URL.isna().sum()),
        "both_url_and_label_missing_rows": int(
            (frame.URL.isna() & frame.ClassLabel.isna()).sum()
        ),
        "model_predictions_performed": False,
    }
    write_json(ROOT / "ml/reports/legitphish-label-schema-inspection.json", report)
    print(json.dumps(report, indent=2), flush=True)


def sanitize_intake(raw):
    counts, records = Counter(), []
    for index, row in enumerate(raw.itertuples(index=False)):
        label = int(row.label)
        counts[f"raw_label_{label}"] += 1
        try:
            prepared = prepare_url(row.url)
            if prepare_experiment_url(row.url).core != prepared.core:
                counts[f"privacy_assignment_excluded_label_{label}"] += 1
                continue
        except InvalidUrl as error:
            counts[f"unsupported_{str(error)}_label_{label}"] += 1
            continue
        records.append(
            {
                "core": prepared.core,
                "digest": prepared.digest,
                "group": prepared.group,
                "representation_digest": representation_digest(prepared.core),
                "label": label,
                "source_row": index,
            }
        )
    result = pd.DataFrame(
        records,
        columns=[
            "core",
            "digest",
            "group",
            "representation_digest",
            "label",
            "source_row",
        ],
    )
    return result, dict(counts)


def collect_exposure():
    paths = [ROOT / "ml/data/indonesia-gold/registry/known-exposure.sqlite"]
    paths.extend(sorted((ROOT / "ml/data/exposure-sidecars").glob("*.sqlite")))
    url_hashes, domain_hashes, manifests = set(), set(), {}
    for path in paths:
        before = checksum(path)
        with sqlite3.connect(
            path.resolve().as_uri() + "?mode=ro", uri=True
        ) as connection:
            url_hashes.update(
                row[0] for row in connection.execute("SELECT value FROM url_hashes")
            )
            domain_hashes.update(
                row[0] for row in connection.execute("SELECT value FROM domain_hashes")
            )
        if checksum(path) != before:
            raise ValueError("exposure_database_changed_during_read")
        manifests[path.relative_to(ROOT).as_posix()] = before
    original = json.loads(
        (ROOT / "ml/reports/v6-development-experiment-protocol.json").read_text()
    )
    for asset in [original["development"], *original["benchmarks"].values()]:
        path = ROOT / "ml/runs/notebook-tfidf-logistic-v6/data" / asset["filename"]
        if checksum(path) != asset["sha256"]:
            raise ValueError("v6_exposure_cache_checksum_mismatch")
        frame = pd.read_parquet(path, columns=["core", "group", "digest"])
        url_hashes.update(frame.digest)
        url_hashes.update(representation_digest(core) for core in frame.core)
        domain_hashes.update(digest(group) for group in frame.group)
        manifests[path.relative_to(ROOT).as_posix()] = asset["sha256"]
    return url_hashes, domain_hashes, manifests


def curate(frame, prior_urls, prior_domains, cap=5):
    counts = {}
    conflicts = frame.groupby("representation_digest").label.nunique()
    conflict_mask = frame.representation_digest.isin(conflicts[conflicts > 1].index)
    counts["conflicting_representations"] = int((conflicts > 1).sum())
    counts["conflicting_rows"] = int(conflict_mask.sum())
    clean = frame.loc[~conflict_mask].sort_values(["source_row"], kind="stable")
    unique = clean.drop_duplicates("representation_digest")
    counts["consistent_duplicate_rows"] = len(clean) - len(unique)
    old_url = unique.digest.isin(prior_urls) | unique.representation_digest.isin(
        prior_urls
    )
    old_domain = unique.group.map(digest).isin(prior_domains)
    for label in (0, 1):
        mask = unique.label.eq(label)
        counts[f"old_url_rows_label_{label}"] = int((mask & old_url).sum())
        counts[f"old_domain_rows_label_{label}"] = int((mask & old_domain).sum())
        counts[f"old_url_or_domain_rows_label_{label}"] = int(
            (mask & (old_url | old_domain)).sum()
        )
    novel = unique.loc[~(old_url | old_domain)].sort_values("digest", kind="stable")
    retained = (
        novel.groupby("group", sort=False).head(cap).copy().reset_index(drop=True)
    )
    counts["pre_domain_cap_rows"] = len(novel)
    counts["domain_cap_excluded_rows"] = len(novel) - len(retained)
    return retained, counts


def write_sidecar(path, frame):
    if path.exists():
        raise ValueError("exposure_sidecar_already_exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE url_hashes (value TEXT PRIMARY KEY NOT NULL)")
        connection.execute(
            "CREATE TABLE domain_hashes (value TEXT PRIMARY KEY NOT NULL)"
        )
        values = set(frame.digest) | set(frame.representation_digest)
        connection.executemany(
            "INSERT INTO url_hashes VALUES (?)", [(value,) for value in sorted(values)]
        )
        groups = {digest(group) for group in frame.group}
        connection.executemany(
            "INSERT INTO domain_hashes VALUES (?)",
            [(value,) for value in sorted(groups)],
        )
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": checksum(path),
        "url_hashes": len(values),
        "domain_hashes": len(groups),
        "scope": "all_supported_privacy_screened_intake_before_curation_not_only_scored_rows",
    }


def prepare(protocol, protocol_path, directory):
    if directory.exists():
        raise ValueError("choose_new_intake_directory")
    artifact = RichArtifact()
    if (
        artifact.manifest["bundle_sha256"] != protocol["artifact_sha256"]
        or artifact.manifest["frozen_metadata_sha256"] != protocol["metadata_sha256"]
    ):
        raise ValueError("frozen_v6_identity_mismatch")
    directory.mkdir(parents=True)
    before = collect_exposure()
    binding = {
        "protocol_sha256": checksum(protocol_path),
        "source_hashes": {name: checksum(ROOT / name) for name in SOURCES},
        "existing_exposure_hashes": before[2],
        "started_at_utc": now(),
    }
    write_json(directory / "started.json", binding)
    content = download_bytes(protocol["dataset"])
    raw, columns, publisher_counts = read_release(content)
    if publisher_counts.get("missing_label_quarantined", 0) and not protocol.get(
        "qa_amendment_before_first_model_predictions"
    ):
        raise ValueError("missing_label_requires_explicit_protocol_amendment")
    del content
    print(
        "Publisher checksum verified; CSV schema and label counts read without printing targets",
        flush=True,
    )
    supported, sanitization = sanitize_intake(raw)
    raw_rows = len(raw) + publisher_counts.get("missing_label_quarantined", 0)
    del raw
    retained, curation = curate(supported, before[0], before[1])
    if set(retained.digest).intersection(before[0]) or set(
        retained.group.map(digest)
    ).intersection(before[1]):
        raise ValueError("retained_exposure_overlap")
    cache = directory / "sanitized-domain-disjoint.parquet"
    retained.to_parquet(cache, index=False)
    exposure = write_sidecar(
        ROOT / "ml/data/exposure-sidecars/legitphish-v2-20261105.sqlite", supported
    )
    metadata = {
        **binding,
        "frozen_at_utc": now(),
        "downloaded_asset_sha256": protocol["dataset"]["sha256"],
        "downloaded_asset_bytes": protocol["dataset"]["bytes"],
        "raw_rows": raw_rows,
        "csv_columns": columns,
        "publisher_label_counts": publisher_counts,
        "label_mapping_inverted_to_project": True,
        "sanitization": sanitization,
        "supported_privacy_screened_rows": len(supported),
        "curation": curation,
        "retained_rows": len(retained),
        "retained_groups": int(retained.group.nunique()),
        "retained_class_counts": {
            str(k): int(v) for k, v in retained.label.value_counts().items()
        },
        "retained_class_domain_counts": {
            str(label): int(retained.loc[retained.label.eq(label), "group"].nunique())
            for label in (0, 1)
        },
        "cache_path": cache.relative_to(ROOT).as_posix(),
        "cache_sha256": checksum(cache),
        "exposure_sidecar": exposure,
        "raw_urls_persisted": False,
        "model_scores_used_for_curation": False,
        "targets_visited": False,
        "publisher_counts_discrepancy": raw_rows != 101219,
    }
    for relative, expected in before[2].items():
        if checksum(ROOT / relative) != expected:
            raise ValueError("historical_exposure_changed")
    write_json(directory / "frozen-intake.json", metadata)
    write_json(
        ROOT / "ml/provenance/legitphish-v2-exposure.json",
        {
            "created_at_utc": now(),
            "source": protocol["dataset"]["doi"],
            "intake_manifest": (directory / "frozen-intake.json")
            .relative_to(ROOT)
            .as_posix(),
            "intake_manifest_sha256": checksum(directory / "frozen-intake.json"),
            "sidecar": exposure,
            "require_union_with_historical_registry_for_future_novelty_claims": True,
        },
    )
    print(
        json.dumps(
            {
                "raw_rows": raw_rows,
                "retained_rows": len(retained),
                "retained_classes": metadata["retained_class_counts"],
            }
        ),
        flush=True,
    )


def evaluate(protocol, protocol_path, directory, output):
    if any(output.with_suffix(suffix).exists() for suffix in (".json", ".md", ".png")):
        raise ValueError("completed_external_evaluation_already_exists")
    intake = json.loads((directory / "frozen-intake.json").read_text())
    if checksum(protocol_path) != intake["protocol_sha256"] or any(
        checksum(ROOT / name) != value
        for name, value in intake["source_hashes"].items()
    ):
        raise ValueError("external_evaluation_source_or_protocol_changed")
    if checksum(ROOT / intake["cache_path"]) != intake["cache_sha256"]:
        raise ValueError("external_evaluation_cache_changed")
    for path, expected in intake["existing_exposure_hashes"].items():
        if checksum(ROOT / path) != expected:
            raise ValueError("external_evaluation_exposure_changed")
    sidecar = intake["exposure_sidecar"]
    if checksum(ROOT / sidecar["path"]) != sidecar["sha256"]:
        raise ValueError("external_intake_sidecar_changed")
    integrity = validate()
    artifact = RichArtifact()
    if artifact.metadata["thresholds"] != protocol["thresholds"]:
        raise ValueError("original_thresholds_changed")
    frame = pd.read_parquet(ROOT / intake["cache_path"])
    levels = {}
    counts = frame.label.value_counts()
    both_classes = all(
        counts.get(label, 0) >= protocol["minimum_for_binary_scoring"][name]
        for label, name in [(0, "benign"), (1, "phishing")]
    )
    if both_classes:
        with threadpool_limits(limits=4):
            scores = artifact.predict_cores(frame.core)
        for name, threshold in protocol["thresholds"].items():
            result = safe_metrics(frame, scores, threshold)
            result["domain_bootstrap95"] = domain_intervals(
                frame,
                scores,
                threshold,
                protocol["uncertainty"]["domain_bootstrap_repeats"],
                protocol["uncertainty"]["seed"],
            )
            levels[name] = result
        print(
            "Frozen model scores completed on eligible domain-disjoint rows", flush=True
        )
    else:
        scores = None
        print("No valid two-class retained cohort; binary metrics withheld", flush=True)
    final = validate()
    if final["artifact_sha256"] != integrity["artifact_sha256"]:
        raise ValueError("frozen_model_changed_during_evaluation")
    report = {
        "completed_at_utc": now(),
        "protocol_sha256": checksum(protocol_path),
        "intake": intake,
        "runtime_integrity": final,
        "scope": protocol["scope"],
        "binary_evaluation_performed": both_classes,
        "metrics": levels,
        "training_performed": False,
        "thresholds_changed": False,
        "new_release_external_benchmark": True,
        "independent_campaigns_verified": False,
        "Indonesia_gold_verified": False,
        "production_ready": False,
        "limitations": protocol["limitations"],
    }
    if both_classes:
        flags = pd.DataFrame(
            [
                {
                    "private_hosting": bool(EXTRACT(prepare_url(core).host).is_private),
                    "root_path": prepare_url(core).path == "/",
                    "long_url": len(core.split("://", 1)[1]) > 120,
                }
                for core in frame.core
            ]
        )
        report["warning_structural_slices"] = {
            name + ("_yes" if value else "_no"): safe_metrics(
                frame.loc[flags[name].eq(value)],
                scores[flags[name].eq(value).to_numpy()],
                protocol["thresholds"]["warning"],
            )
            for name in flags
            for value in (True, False)
        }
        report["class_concentration"] = {
            str(label): {
                "domains": int(frame.loc[frame.label.eq(label), "group"].nunique()),
                "largest_single_domain_share": float(
                    frame.loc[frame.label.eq(label), "group"].value_counts().max()
                    / counts[label]
                ),
            }
            for label in (0, 1)
        }
    write_json(output.with_suffix(".json"), report)
    render_report(output.with_suffix(".md"), report)
    if both_classes:
        render_plot(output.with_suffix(".png"), report)


def render_report(path, report):
    intake = report["intake"]
    lines = [
        "# Frozen v6 pada LegitPhish V2",
        "",
        "Evaluasi eksternal historis mengikuti label penerbit. Model dan threshold v6 asli dipakai tanpa fitting. Cakupan global; tidak mengklaim gold Indonesia atau holdout temporal dua kelas 2026.",
        "",
        f"Sumber: [LegitPhish V2](https://data.mendeley.com/datasets/hx4m73v2sf/2), DOI 10.17632/hx4m73v2sf.2, CC BY 4.0. File `{intake['downloaded_asset_sha256']}` diverifikasi sebelum parsing; raw CSV hanya dibaca di memori.",
        "",
        f"CSV aktual: **{intake['raw_rows']:,} baris**; label penerbit `{json.dumps(intake['publisher_label_counts'], sort_keys=True)}`. Mapping dibalik menjadi benign=0/phishing=1. Klaim total publik 101.219 berbeda dari file jika flag discrepancy bernilai `{intake['publisher_counts_discrepancy']}`.",
        "",
        f"Lolos parser dan guard privasi: {intake['supported_privacy_screened_rows']:,}. Retained setelah konflik, duplikat, paparan URL/domain lama dan cap 5/domain: **{intake['retained_rows']:,} baris**, {intake['retained_groups']:,} domain/private tenant, kelas `{json.dumps(intake['retained_class_counts'], sort_keys=True)}`, domain per kelas `{json.dumps(intake['retained_class_domain_counts'], sort_keys=True)}`.",
        "",
        "## Hasil pada cohort yang tersisa",
        "",
    ]
    if report["binary_evaluation_performed"]:
        lines += [
            "| Policy asli | Accuracy | Precision | Recall phishing | FPR | TP | FN | FP | TN |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for name, row in report["metrics"].items():
            count = row["confusion_matrix"]
            lines.append(
                f"| {name} | {row['accuracy']:.3%} | {row['precision']:.3%} | {row['recall']:.3%} | {row['fpr']:.3%} | {count['tp']} | {count['fn']} | {count['fp']} | {count['tn']} |"
            )
        warning = report["metrics"]["warning"]
        lines += [
            "",
            f"Domain bootstrap 95% warning: recall `{warning['domain_bootstrap95']['recall95']}`, FPR `{warning['domain_bootstrap95']['fpr95']}` (rasio 0–1). Brier {warning['brier_score']:.6f}; log loss {warning['log_loss']:.6f}; ECE {warning['ece_10_fixed_bins']:.6f}. Interval Wilson, balanced accuracy dan reliability bins ada pada JSON.",
            "",
            "Angka hanya berlaku pada subset label penerbit yang tersisa. Attrition dan cap domain mengubah distribusi sumber; precision bukan precision trafik. Label phishing-vs-malware belum diverifikasi independen, dan overlap kampanye tidak diketahui.",
        ]
    else:
        lines += [
            "Cohort yang tersisa tidak mendukung evaluasi dua kelas. Accuracy, precision dan FPR biner tidak dihitung. Kekurangan kelas/domain harus diselesaikan dengan bukti baru; tidak menggabungkan benign historis secara otomatis."
        ]
    lines += [
        "",
        "## Audit intake",
        "",
        "```json",
        json.dumps(
            {"sanitization": intake["sanitization"], "curation": intake["curation"]},
            indent=2,
        ),
        "```",
        "",
        "Jumlah old_url dan old_domain dapat tumpang tindih; old_url_or_domain adalah gabungannya. Baris dengan konflik label dikarantina tanpa relabel. Guard assignment path mengecualikan input jika redaksi tambahan akan mengubah representasi frozen v6. Parser tetap heuristik dan tidak membuktikan anonimisasi lengkap.",
        "",
        "Hash seluruh intake yang lolos privasi dicatat dalam sidecar exposure lokal, termasuk baris yang akhirnya dikeluarkan dari skor. Registry lama utuh; pemeriksaan novelty berikutnya wajib memakai gabungan registry, sidecar dan cache v6. Dataset/core/hash target tetap diabaikan Git.",
        "",
        "## Provenance label dan batas kesimpulan",
        "",
        "[Metode artikel](https://pmc.ncbi.nlm.nih.gov/articles/PMC12538017/) menyebut pemeriksaan manual atau pencocokan threat feed; tidak ada bukti dua reviewer independen untuk setiap baris. Tanggal publikasi tidak membuktikan waktu observasi tiap URL. Klaim hasil paper lain tidak dipindahkan menjadi hasil v6.",
        "",
    ]
    lines += ["- " + item for item in report["limitations"]]
    lines += [
        "",
        "Reproduksi dari cache lokal yang sudah dibekukan:",
        "",
        "```powershell",
        "ml/.venv/Scripts/python.exe scripts/evaluate_legitphish_v6.py --stage evaluate --output-stem ml/reports/legitphish-v6-replay",
        "```",
        "",
        "Replay tetap dataset teramati. Gunakan extra `quality` untuk parquet/grafik; artifact dan cache lokal diperlukan.",
        "",
    ]
    path.write_bytes("\n".join(lines).encode())


def render_plot(path, report):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = report["metrics"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    for ax, key, title in [
        (axes[0], "recall", "Phishing recall"),
        (axes[1], "fpr", "False-positive rate"),
    ]:
        values = [rows[name][key] * 100 for name in rows]
        ax.bar(list(rows), values, color=["#176b87", "#db8f38"])
        ax.set(ylim=(0, 105), ylabel="Percent", title=title)
        for index, value in enumerate(values):
            ax.text(index, value + 2, f"{value:.2f}%", ha="center")
    fig.suptitle(
        "Frozen v6 on curated LegitPhish publisher labels\nGlobal historical subset; campaign independence and Indonesia gold not established"
    )
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage", choices=["inspect", "prepare", "evaluate", "all"], default="all"
    )
    parser.add_argument(
        "--directory", type=Path, default=ROOT / "ml/data/legitphish-v2-v6-qa"
    )
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument(
        "--output-stem", type=Path, default=ROOT / "ml/reports/legitphish-v6-evaluation"
    )
    args = parser.parse_args()
    directory, output = args.directory.resolve(), args.output_stem.resolve()
    if not directory.is_relative_to(ROOT / "ml/data") or not output.is_relative_to(
        ROOT / "ml/reports"
    ):
        raise ValueError("external_evaluation_path_outside_workspace_scope")
    protocol = json.loads(args.protocol.read_text())
    if args.stage == "inspect":
        inspect_labels(protocol["dataset"])
        return
    if args.stage in ("prepare", "all"):
        prepare(protocol, args.protocol, directory)
    if args.stage in ("evaluate", "all"):
        evaluate(protocol, args.protocol, directory, output)


if __name__ == "__main__":
    main()
