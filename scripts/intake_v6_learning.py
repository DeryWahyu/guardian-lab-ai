"""Pin two historical research releases; reserve Ebbu exclusively for evaluation."""

import hashlib
import io
import json
from urllib.parse import urlsplit

import pandas as pd
import requests

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from evaluate_legitphish_v6 import collect_exposure, digest, write_sidecar
from evaluate_v6_indonesia_external import prior_identities, verify_files
from experiment_v6_expanded_data import curate_new, now, write_json
from intake_v6_expansion import sanitize_source
from v6_development_support import assert_separated, representation_digest
from v6_indonesia_external_support import coverage

PROTOCOL = ROOT / "ml/reports/v6-learning-20261106-protocol.json"
DATA = ROOT / "ml/data/v6-learning-20261106"


def download(asset):
    address = urlsplit(asset["download_url"])
    if address.scheme != "https" or address.netloc != "raw.githubusercontent.com":
        raise ValueError("unapproved_research_download_host")
    with requests.get(
        asset["download_url"], stream=True, timeout=45, allow_redirects=False
    ) as r:
        if r.status_code != 200:
            raise ValueError("research_download_not_200")
        chunks, size = [], 0
        for chunk in r.iter_content(1024 * 1024):
            size += len(chunk)
            if size > asset["bytes"]:
                raise ValueError("research_download_too_large")
            chunks.append(chunk)
    content = b"".join(chunks)
    if (
        len(content) != asset["bytes"]
        or hashlib.sha256(content).hexdigest() != asset["sha256"]
    ):
        raise ValueError("research_download_hash_or_size_mismatch")
    return content


def main():
    if DATA.exists():
        raise ValueError("learning_intake_requires_new_directory")
    p = json.loads(PROTOCOL.read_text())
    files = [
        "scripts/intake_v6_learning.py",
        "scripts/intake_v6_expansion.py",
        "scripts/evaluate_legitphish_v6.py",
        "scripts/evaluate_v6_indonesia_external.py",
        "scripts/experiment_v6_expanded_data.py",
        "scripts/v6_development_support.py",
        "scripts/v6_indonesia_external_support.py",
        "ml/src/guardian_ml/preprocessing.py",
    ]
    bindings = {f: checksum(ROOT / f) for f in files}
    protocol_hash = checksum(PROTOCOL)
    print(
        "Checking all prior exposure and actual development/test identities", flush=True
    )
    urls, domains, prior = collect_exposure()
    identities = prior_identities(urls, domains)
    latest = ROOT / "ml/data/v6-indonesia-external-20261106/frozen.json"
    latest_data = json.loads(latest.read_text())
    # Bind every cached partition of the latest intake, especially the unscored reserve.
    for path in sorted(latest.parent.glob("*.parquet")):
        identities[path.relative_to(ROOT).as_posix()] = checksum(path)
        frame = pd.read_parquet(path, columns=["core", "group", "digest"])
        urls.update(frame.digest)
        urls.update(representation_digest(core) for core in frame.core)
        domains.update(digest(group) for group in frame.group)
    verify_files({latest_data["sidecar"]["path"]: latest_data["sidecar"]["sha256"]})
    parts, audits = [], {}
    for source in p["intake"]["sources"]:
        frames = []
        for asset in source["files"]:
            content = download(asset)
            values = (
                json.loads(content)
                if asset["format"] == "json_list"
                else pd.read_csv(io.BytesIO(content), header=None)[0].tolist()
            )
            if len(values) != asset["rows"] or not all(
                isinstance(x, str) for x in values
            ):
                raise ValueError("research_publisher_schema_mismatch")
            frames.append(pd.DataFrame({"url": values, "label": asset["label"]}))
            del content, values
        frame, audit = sanitize_source(
            pd.concat(frames, ignore_index=True), source["name"], "url", "label"
        )
        frame["label"] = frame.publisher_label.map({"0": 0, "1": 1}).astype(int)
        frame = frame.drop(columns="publisher_label")
        parts.append(frame)
        audits[source["name"]] = audit
        print(
            json.dumps({"source": source["name"], "sanitized_rows": len(frame)}),
            flush=True,
        )
    supported = pd.concat(parts, ignore_index=True)
    novel, curation = curate_new(parts, urls, domains, p["intake"]["curation"])
    external_groups = set(
        supported.loc[supported.training_source.eq("ebbu2017"), "group"]
    )
    cross = novel.training_source.eq("iscx2016_replica") & novel.group.isin(
        external_groups
    )
    curation["iscx_cross_publisher_domain_exclusions"] = int(cross.sum())
    novel = novel.loc[~cross].copy()
    novel.loc[novel.training_source.eq("ebbu2017"), "partition"] = "ebbu_external"
    novel.loc[novel.partition.eq("new_test"), "partition"] = "iscx_external"
    DATA.mkdir(parents=True)
    supported.to_parquet(DATA / "supported.parquet", index=False)
    assets, separated = {}, []
    for name in ("fit", "ebbu_external", "iscx_external"):
        frame = novel.loc[novel.partition.eq(name)].reset_index(drop=True)
        frame.to_parquet(DATA / (name + ".parquet"), index=False)
        assets[name] = {
            "path": (DATA / (name + ".parquet")).relative_to(ROOT).as_posix(),
            "sha256": checksum(DATA / (name + ".parquet")),
            **coverage(frame),
        }
        separated.append(frame)
    assert_separated(separated)
    sidecar = write_sidecar(
        ROOT / "ml/data/exposure-sidecars/ebbu-iscx-learning-20261106.sqlite", supported
    )
    verify_files(bindings)
    verify_files(prior)
    verify_files(identities)
    if checksum(PROTOCOL) != protocol_hash:
        raise ValueError("learning_protocol_changed_during_intake")
    frozen = {
        "frozen_at_utc": now(),
        "protocol_sha256": protocol_hash,
        "source_hashes": bindings,
        "prior_exposure_hashes": prior,
        "actual_prior_identity_bindings": identities,
        "sidecar": sidecar,
        "assets": assets,
        "audit": audits,
        "curation": curation,
        "supported_path": (DATA / "supported.parquet").relative_to(ROOT).as_posix(),
        "supported_sha256": checksum(DATA / "supported.parquet"),
        "external_labels": "historical publisher labels; not independent human or Indonesia gold",
        "production_ready": False,
    }
    write_json(DATA / "frozen.json", frozen)
    write_json(
        ROOT / "ml/provenance/ebbu-iscx-learning-exposure.json",
        {
            "sidecar": sidecar,
            "intake_freeze_sha256": checksum(DATA / "frozen.json"),
            "scope": "all sanitized supported inputs, including exclusions, fitting and both external reserves",
            "future_novelty_audits_must_include": True,
        },
    )
    print(json.dumps({"assets": assets, "curation": curation}), flush=True)


if __name__ == "__main__":
    main()
