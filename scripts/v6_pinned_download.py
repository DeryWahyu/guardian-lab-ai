"""Bounded HTTPS range download into memory for pinned public Mendeley files."""

import hashlib
from urllib.parse import urljoin, urlsplit

import requests


def allowed(url):
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    return (
        parsed.scheme == "https"
        and not parsed.username
        and not parsed.password
        and (
            host == "data.mendeley.com"
            or (".s3" in host and host.endswith(".amazonaws.com"))
        )
    )


def download_pinned(asset, session=None, chunk_bytes=4 * 1024 * 1024):
    if (
        not 1 <= chunk_bytes <= 8 * 1024 * 1024
        or not 0 < asset["bytes"] <= 128 * 1024 * 1024
    ):
        raise ValueError("invalid_pinned_download_limits")
    session = session or requests.Session()
    session.trust_env = False
    url, content, redirects = asset["download_url"], bytearray(), 0
    while len(content) < asset["bytes"]:
        start = len(content)
        end = min(start + chunk_bytes, asset["bytes"]) - 1
        for attempt in range(3):
            if not allowed(url):
                raise ValueError("unapproved_pinned_publisher_host")
            try:
                with session.get(
                    url,
                    stream=True,
                    allow_redirects=False,
                    timeout=(15, 45),
                    headers={
                        "Range": f"bytes={start}-{end}",
                        "Accept-Encoding": "identity",
                        "User-Agent": "GuardianLabAI-pinned-public-research/1.0",
                    },
                ) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        redirects += 1
                        if redirects > 5:
                            raise ValueError("pinned_publisher_redirect_limit")
                        url = urljoin(url, response.headers["Location"])
                        if not allowed(url):
                            raise ValueError("unapproved_pinned_publisher_redirect")
                        continue
                    if response.status_code != 206:
                        raise ValueError("pinned_publisher_range_required")
                    if (
                        response.headers.get("Content-Range")
                        != f"bytes {start}-{end}/{asset['bytes']}"
                    ):
                        raise ValueError("pinned_publisher_content_range_mismatch")
                    block = bytearray()
                    for chunk in response.iter_content(65536):
                        block.extend(chunk)
                        if len(block) > end - start + 1:
                            raise ValueError("pinned_publisher_range_oversize")
                    if len(block) != end - start + 1:
                        raise requests.exceptions.ChunkedEncodingError(
                            "short_publisher_block"
                        )
                content.extend(block)
                break
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError,
            ):
                if attempt == 2:
                    raise ValueError("pinned_publisher_transfer_incomplete") from None
        else:
            raise ValueError("pinned_publisher_range_attempts_exhausted")
    if hashlib.sha256(content).hexdigest() != asset["sha256"]:
        raise ValueError("pinned_publisher_sha256_mismatch")
    return bytes(content)
