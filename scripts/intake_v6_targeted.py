"""Read pinned publisher SQL as data, sanitize in memory, never execute SQL."""

import json
import re

import pandas as pd

from guardian_ml.metadata import checksum
from guardian_ml.paths import ROOT
from evaluate_legitphish_v6 import download_bytes, write_json
from intake_v6_expansion import sanitize_source

PROTOCOL = ROOT / "ml/reports/v6-targeted-20261105-protocol.json"
DIRECTORY = ROOT / "ml/data/v6-targeted-20261105"
INSERT = re.compile(r"INSERT\s+INTO\s+`?\w+`?\s*\(([^)]+)\)\s*VALUES\s*", re.I)
LITERAL = re.compile(r"\s*(NULL|'(?:[^'\\]|\\.|'')*'|[-+]?\d+(?:\.\d+)?)\s*", re.I)


def unquote_sql(token):
    if token.upper() == "NULL":
        return None
    if not token.startswith("'"):
        return token
    escapes = {"n": "\n", "r": "\r", "t": "\t", "0": "\0", "Z": "\x1a"}
    text = token[1:-1].replace("''", "'")
    return re.sub(r"\\(.)", lambda m: escapes.get(m[1], m[1]), text, flags=re.S)


def read_sql_records(content, columns):
    """Accept literal INSERT rows only; SQL expressions are never evaluated."""
    text = content.decode("utf-8-sig")
    rows, statements = [], 0
    if re.search(r"^\s*(DELETE|UPDATE)\s", text, re.I | re.M):
        raise ValueError("mutable_sql_requires_publisher_schema_review")
    for match in INSERT.finditer(text):
        actual = [item.strip().strip("`") for item in match[1].split(",")]
        if actual != columns:
            raise ValueError("publisher_sql_column_mismatch")
        position = match.end()
        statements += 1
        while True:
            while position < len(text) and text[position].isspace():
                position += 1
            if position >= len(text) or text[position] != "(":
                raise ValueError("publisher_sql_expected_literal_tuple")
            position += 1
            row = []
            for index in range(len(columns)):
                literal = LITERAL.match(text, position)
                if not literal:
                    raise ValueError("publisher_sql_nonliteral_value_rejected")
                row.append(unquote_sql(literal[1]))
                position = literal.end()
                expected = ")" if index == len(columns) - 1 else ","
                if position >= len(text) or text[position] != expected:
                    raise ValueError("publisher_sql_tuple_arity_or_expression_rejected")
                position += 1
            rows.append(row)
            while position < len(text) and text[position].isspace():
                position += 1
            if position < len(text) and text[position] == ";":
                break
            if position >= len(text) or text[position] != ",":
                raise ValueError("publisher_sql_unterminated_insert")
            position += 1
    if not rows or len(rows) > 100000:
        raise ValueError("publisher_sql_unexpected_record_count")
    frame = pd.DataFrame(rows, columns=columns)
    if frame.rec_id.duplicated().any() or not frame.result.isin(["0", "1"]).all():
        raise ValueError("publisher_sql_identifier_or_label_schema_invalid")
    return frame, {"literal_insert_statements": statements, "sql_executed": False}


def main():
    protocol = json.loads(PROTOCOL.read_text())
    output = DIRECTORY / "pwd2021-sanitized.parquet"
    if output.exists():
        raise ValueError("targeted_intake_already_completed")
    content = download_bytes(protocol["new_source"])
    frame, parsing = read_sql_records(
        content, protocol["new_source"]["expected_columns"]
    )
    retained, audit = sanitize_source(frame, "pwd2021", "url", "result")
    retained["label"] = retained.publisher_label.astype(int)
    retained = retained.drop(columns="publisher_label")
    del content, frame
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    retained.to_parquet(output, index=False)
    audit.update(parsing)
    audit.update(
        {
            "asset": protocol["new_source"],
            "cache_sha256": checksum(output),
            "protocol_sha256": checksum(PROTOCOL),
            "intake_source_sha256": checksum(__file__),
            "raw_urls_persisted": False,
            "targets_visited": False,
            "independent_human_gold": False,
            "Indonesia_gold": False,
        }
    )
    write_json(DIRECTORY / "intake.json", audit)
    print(json.dumps({k: v for k, v in audit.items() if k != "asset"}), flush=True)


if __name__ == "__main__":
    main()
