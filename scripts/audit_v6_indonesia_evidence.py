"""Census prescribed Indonesia filenames without exposing case or reviewer data."""

import csv
import json

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from audit_v6_human_review import completed_review, inspect_pair
from experiment_v6_expanded_data import now, write_json

NAMES = tuple(
    "indonesia-" + name + ".csv"
    for name in (
        "candidates",
        "reviewer-a",
        "reviewer-b",
        "adjudication",
        "error-review",
    )
)


def census(directory, templates):
    result = {}
    for name in NAMES:
        path = directory / name
        if not path.exists():
            result[name] = {"exists": False, "rows": 0}
            continue
        with (templates / name).open(encoding="utf-8-sig", newline="") as stream:
            expected = next(csv.reader(stream))
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != expected:
                raise ValueError("indonesia_input_schema_mismatch")
            rows = list(reader)
        result[name] = {"exists": True, "rows": len(rows), "sha256": checksum(path)}
        if "reviewer-" in name:
            result[name]["syntactically_complete_attested_reviews"] = sum(
                completed_review(row) for row in rows
            )
    return result


def main():
    external = ROOT / "ml/reports/v6-indonesia-external-evaluation.json"
    directory = ROOT / "ml/data/v6-weighted-review-20261105"
    report = {
        "audited_at_utc": now(),
        "source_sha256": checksum(__file__),
        "supersedes_human_input_census_in": external.relative_to(ROOT).as_posix(),
        "external_report_sha256": checksum(external),
        "correction": "Frozen external evaluator checked unprefixed filenames. This supplemental census checks the actual indonesia-*.csv filenames and template schemas. Frozen metrics, model artifacts, code and original report remain unchanged.",
        "indonesia_inputs": census(
            ROOT / "ml/data/indonesia-gold/input", ROOT / "ml/templates"
        ),
        "development_review": inspect_pair(
            directory / "conflict-reviewer-a.csv", directory / "conflict-reviewer-b.csv"
        ),
        "user_reported_reviewers_available": False,
        "independent_human_identity_established": False,
        "independent_indonesia_gold_evaluation_completed": False,
        "indonesia_gold_metrics": None,
        "production_ready": False,
    }
    write_json(ROOT / "ml/reports/v6-indonesia-evidence-status.json", report)
    print(
        json.dumps(
            {
                "indonesia_rows": {
                    k: v["rows"] for k, v in report["indonesia_inputs"].items()
                },
                "development_review_cases": report["development_review"]["cases"],
                "complete_development_pairs": report["development_review"][
                    "complete_attested_pairs"
                ],
            }
        )
    )


if __name__ == "__main__":
    main()
