"""Network boundaries and byte integrity for public publisher downloads."""

import hashlib
import importlib
import sys

import pytest
import requests

from guardian_ml.paths import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
download = importlib.import_module("v6_pinned_download")
sys.path.pop(0)


class Response:
    def __init__(self, code, headers, content=b"", broken=False):
        self.status_code, self.headers, self.content, self.broken = code, headers, content, broken

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def iter_content(self, _):
        if self.broken:
            raise requests.exceptions.ChunkedEncodingError("partial")
        yield self.content


class Session:
    def __init__(self, responses):
        self.responses, self.urls = iter(responses), []

    def get(self, url, **_):
        self.urls.append(url)
        return next(self.responses)


def asset():
    return {
        "download_url": "https://data.mendeley.com/public-files/example",
        "bytes": 8,
        "sha256": hashlib.sha256(b"abcdefgh").hexdigest(),
    }


def block(start, value, **options):
    return Response(206, {"Content-Range": f"bytes {start}-{start + 3}/8"}, value, **options)


def test_exact_range_chunks_are_reassembled_and_verified():
    session = Session([block(0, b"abcd"), block(4, b"efgh")])
    assert download.download_pinned(asset(), session, 4) == b"abcdefgh"


def test_partial_network_transfer_retries_same_range_without_duplicate_bytes():
    session = Session([block(0, b"", broken=True), block(0, b"abcd"), block(4, b"efgh")])
    assert download.download_pinned(asset(), session, 4) == b"abcdefgh"


def test_dataset_target_redirect_is_rejected_before_requesting_target():
    session = Session([Response(302, {"Location": "https://target.invalid/credential"})])
    with pytest.raises(ValueError, match="unapproved_pinned_publisher_redirect"):
        download.download_pinned(asset(), session, 4)
    assert session.urls == [asset()["download_url"]]


@pytest.mark.parametrize(
    "response,error",
    [
        (Response(200, {}, b"abcdefgh"), "range_required"),
        (Response(206, {"Content-Range": "bytes 1-4/8"}, b"abcd"), "content_range_mismatch"),
        (block(0, b"abcde"), "oversize"),
    ],
)
def test_bad_http_range_responses_are_rejected(response, error):
    with pytest.raises(ValueError, match=error):
        download.download_pinned(asset(), Session([response]), 4)


def test_whole_file_checksum_is_required_even_with_correct_range_sizes():
    with pytest.raises(ValueError, match="sha256_mismatch"):
        download.download_pinned(asset(), Session([block(0, b"xxxx"), block(4, b"efgh")]), 4)
