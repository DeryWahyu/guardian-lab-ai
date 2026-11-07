"""Read actual review files, report missing work, never create reviewers or case labels."""

import csv
from datetime import datetime
import json
from pathlib import Path

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from experiment_v6_expanded_data import now, write_json

LABELS = {"benign", "phishing", "uncertain", "out_of_scope"}
BLIND_COLUMNS = {
    "case_id",
    "cache_digest",
    "cache_filename",
    "reviewer_id",
    "label",
    "confidence",
    "reason_code",
    "evidence_ref",
    "human_review_confirmed",
    "reviewed_at",
}


def completed_review(row):
    if (
        row.get("label") not in LABELS
        or not row.get("reviewer_id", "").strip()
        or not row.get("confidence", "").strip()
        or row.get("human_review_confirmed", "").strip().lower() != "true"
        or not row.get("reason_code", "").strip()
        or not row.get("evidence_ref", "").strip()
    ):
        return False
    try:
        timestamp = datetime.fromisoformat(
            row.get("reviewed_at", "").replace("Z", "+00:00")
        )
        return timestamp.tzinfo is not None
    except ValueError:
        return False


def inspect_pair(first: Path, second: Path):
    packs, files = [], {}
    for path in (first, second):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if set(reader.fieldnames or []) != BLIND_COLUMNS:
                raise ValueError("review_pack_must_remain_blind_and_hash_only")
            rows = list(reader)
        ids = [row["case_id"] for row in rows]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_review_case_id")
        pack = {row["case_id"]: row for row in rows}
        packs.append(pack)
        files[path.name] = {
            "rows": len(rows),
            "complete_attested_reviews": sum(completed_review(row) for row in rows),
            "sha256": checksum(path),
        }
    if packs[0].keys() != packs[1].keys():
        raise ValueError("review_pack_case_sets_do_not_match")
    complete_pairs, same_reviewer, locator_mismatch, disagreement = 0, 0, 0, 0
    for identity, row in packs[0].items():
        other = packs[1][identity]
        locator_mismatch += any(
            row[k] != other[k] for k in ("cache_digest", "cache_filename")
        )
        if completed_review(row) and completed_review(other):
            same_reviewer += (
                row["reviewer_id"].strip().casefold()
                == other["reviewer_id"].strip().casefold()
            )
            complete_pairs += 1
            disagreement += row["label"] != other["label"]
    if locator_mismatch:
        raise ValueError("review_case_locator_mismatch")
    return {
        "files": files,
        "cases": len(packs[0]),
        "complete_attested_pairs": complete_pairs,
        "same_reviewer_id_pairs_rejected": same_reviewer,
        "label_disagreements": disagreement,
        "independence_established": False,
        "identity_evidence_and_coordinator_independence_check_required": True,
        "automatic_label_changes": 0,
        "human_gold_established": False,
    }


def main():
    directory = ROOT / "ml/data/v6-weighted-review-20261105"
    result = inspect_pair(
        directory / "conflict-reviewer-a.csv", directory / "conflict-reviewer-b.csv"
    )
    indonesia = {}
    for path in sorted((ROOT / "ml/data/indonesia-gold/input").glob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = sum(1 for _ in csv.DictReader(stream))
        indonesia[path.name] = {"rows": rows, "sha256": checksum(path)}
    report = {
        "audited_at_utc": now(),
        "user_reported_reviewers_available": False,
        "development_review": result,
        "Indonesia_inputs": indonesia,
        "Indonesia_gold_established": False,
        "production_ready": False,
    }
    write_json(ROOT / "ml/reports/v6-segmented-human-review-status.json", report)
    print(
        json.dumps(
            {
                "review_cases": result["cases"],
                "complete_attested_pairs": result["complete_attested_pairs"],
                "reviewers_available": False,
                "Indonesia_rows": {k: v["rows"] for k, v in indonesia.items()},
            }
        )
    )


if __name__ == "__main__":
    main()
