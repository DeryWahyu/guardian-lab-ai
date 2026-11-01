"""Privacy and train/inference parity regressions with synthetic examples only."""

import pytest
from guardian_ml.preprocessing import prepare_url, InvalidUrl
from guardian_ml.features import feature_frame, SCHEMA


def test_query_and_fragment_do_not_change_core_or_features():
    plain = prepare_url("https://example.org/login")
    private = prepare_url("https://example.org/login?email=person%40example.net#private")
    assert plain == private
    assert feature_frame([plain.core]).equals(feature_frame([private.core]))


def test_private_suffix_tenants_are_separate_groups():
    assert prepare_url("https://alice.github.io/path").group == "alice.github.io"
    assert prepare_url("https://bob.github.io/path").group == "bob.github.io"
    assert prepare_url("https://login.bank.co.id/path").group == "bank.co.id"


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.org/path",
        "mailto:person@example.org",
        "wifi:example",
        "https://localhost/",
        "http://127.0.0.1/",
        "http://169.254.169.254/",
        "https://user:password@example.org/",
        "https://example.org/\nprivate",
        "https://example.org/%250Aprivate",
        "https://example.org/%252540private",
        "https://example.org/" + "a" * 16384,
        "https://example.org:99999/",
    ],
)
def test_out_of_scope_inputs_are_rejected_without_echoing_input(url):
    with pytest.raises(InvalidUrl) as raised:
        prepare_url(url)
    assert url not in str(raised.value)


@pytest.mark.parametrize(
    "tail",
    [
        "person%2540example.net",
        "081234567890",
        "1234567890123456",
        "token/synthetic-secret-value",
        "password/synthetic-password",
        "abc123abc123abc123abc123abc123",
    ],
)
def test_path_sensitive_patterns_are_redacted(tail):
    prepared = prepare_url("https://example.org/" + tail)
    assert "REDACTED" in prepared.core
    assert prepare_url(prepared.core).core == prepared.core


def test_normalization_is_idempotent():
    parsed = prepare_url("HTTPS://EXAMPLE.ORG:443/a%20b")
    assert parsed.core == "https://example.org/a%20b"
    assert prepare_url(parsed.core).core == parsed.core
    assert prepare_url("example.org/a").core == "https://example.org/a"


def test_idn_and_public_ipv6():
    assert "xn--" in prepare_url("https://bücher.de/").host
    assert prepare_url("https://[2606:4700:4700::1111]/").suffix == "ip"


def test_feature_schema_contains_no_collection_or_query_fields():
    frame = feature_frame(["https://example.org/login?token=discarded"])
    assert list(frame.columns) == SCHEMA
    assert not {"date", "source", "label", "group", "query", "raw_url"} & set(frame.columns)


def test_scrubbing_rechecks_tokens_joined_by_a_previous_replacement():
    parsed = prepare_url("https://example.org/head5aaaaaa1234567890123456bbbbbbbbbbbbbbb")
    from guardian_ml.preprocessing import TOKEN, NUMBER

    assert not TOKEN.search(parsed.path)
    assert not NUMBER.search(parsed.path)
    assert prepare_url(parsed.core).core == parsed.core
