"""Versioned URL-only numeric features and bounded categorical suffix."""

from collections import Counter
import math
import numpy as np
import pandas as pd
from .preprocessing import prepare_url, PreparedUrl

VERSION = "url-lexical-v1"
BRANDS = (
    "bca",
    "bni",
    "bri",
    "mandiri",
    "dana",
    "gopay",
    "ovo",
    "shopee",
    "tokopedia",
    "paypal",
    "microsoft",
    "google",
    "apple",
    "facebook",
)
KEYWORDS = (
    "login",
    "signin",
    "verify",
    "secure",
    "account",
    "update",
    "password",
    "confirm",
    "bank",
    "wallet",
    "hadiah",
    "klaim",
    "undangan",
)
NUMERIC = (
    "url_length",
    "host_length",
    "path_length",
    "host_labels",
    "host_hyphens",
    "host_digits",
    "host_digit_ratio",
    "host_entropy",
    "path_entropy",
    "path_depth",
    "path_digits",
    "path_digit_ratio",
    "path_hyphens",
    "path_underscores",
    "path_dots",
    "path_percents",
    "host_max_label",
    "registered_length",
    "subdomain_length",
    "suffix_length",
    "punycode",
    "ip_literal",
    "https",
    "keyword_count",
    "brand_count",
    "brand_in_subdomain",
    "brand_in_path",
    "path_equals",
    "path_at",
    "path_semicolon",
    "path_upper_ratio",
    "path_non_ascii_encoded",
    "download_extension",
    "host_vowel_ratio",
)
CATEGORICAL = ("suffix",)
SCHEMA = list(NUMERIC + CATEGORICAL)


def entropy(text):
    if not text:
        return 0.0
    return -sum(
        (count / len(text)) * math.log2(count / len(text)) for count in Counter(text).values()
    )


def feature_row(parsed: PreparedUrl):
    host, path = parsed.host, parsed.path
    low = parsed.core.lower()
    sub = host[: -len(parsed.group)].rstrip(".") if host.endswith(parsed.group) else ""
    path_low = path.lower()
    digits_host = sum(char.isdigit() for char in host)
    digits_path = sum(char.isdigit() for char in path)
    values = [
        len(parsed.core),
        len(host),
        len(path),
        host.count(".") + 1,
        host.count("-"),
        digits_host,
        digits_host / len(host),
        entropy(host),
        entropy(path),
        len([part for part in path.split("/") if part]),
        digits_path,
        digits_path / max(len(path), 1),
        path.count("-"),
        path.count("_"),
        path.count("."),
        path.count("%"),
        max(map(len, host.split("."))),
        len(parsed.group),
        len(sub),
        len(parsed.suffix),
        int("xn--" in host),
        int(parsed.suffix == "ip"),
        int(parsed.scheme == "https"),
        sum(word in low for word in KEYWORDS),
        sum(word in low for word in BRANDS),
        sum(word in sub for word in BRANDS),
        sum(word in path_low for word in BRANDS),
        path.count("="),
        path.count("@"),
        path.count(";"),
        sum(char.isupper() for char in path) / max(len(path), 1),
        path_low.count("%c") + path_low.count("%e"),
        int(path_low.endswith((".apk", ".exe", ".zip", ".scr"))),
        sum(char in "aeiou" for char in host) / len(host),
    ]
    return dict(zip(NUMERIC, values)) | {"suffix": parsed.suffix}


def feature_frame(cores):
    frame = pd.DataFrame.from_records(
        (feature_row(prepare_url(core)) for core in cores),
        columns=SCHEMA,
    )
    frame[list(NUMERIC)] = frame[list(NUMERIC)].astype(np.float32)
    return frame


def heuristic_scores(features):
    # Research baseline, no domain allowlist or declaration of safety.
    return np.clip(
        0.12 * features.keyword_count.to_numpy()
        + 0.15 * features.brand_in_subdomain.to_numpy()
        + 0.10 * (features.host_length.to_numpy() > 35)
        + 0.15 * (features.host_digit_ratio.to_numpy() > 0.2)
        + 0.15 * features.punycode.to_numpy()
        + 0.20 * features.ip_literal.to_numpy()
        + 0.10 * (features.host_hyphens.to_numpy() >= 3),
        0,
        1,
    )
