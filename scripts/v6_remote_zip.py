"""Read selected public archive members with bounded HTTPS ranges, never extract."""

import io
import re
from urllib.parse import urljoin, urlsplit
import zipfile

import requests


class PublisherRangeFile(io.RawIOBase):
    def __init__(self, url, size, session=None, max_read=64 * 1024 * 1024):
        self.url, self.size, self.position = url, int(size), 0
        self.session = session or requests.Session()
        self.max_read = max_read
        self.etag = None
        self.bytes_downloaded = 0
        self.requests_made = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        target = (
            offset
            if whence == 0
            else (self.position if whence == 1 else self.size) + offset
        )
        if target < 0:
            raise ValueError("negative_archive_seek")
        self.position = target
        return target

    def read(self, size=-1):
        size = min(self.size - self.position, size if size >= 0 else self.size)
        if size <= 0:
            return b""
        if size > self.max_read:
            raise ValueError("archive_range_exceeds_memory_bound")
        start, end, url = self.position, self.position + size - 1, self.url
        for _ in range(4):
            parsed = urlsplit(url)
            if (
                parsed.scheme != "https"
                or parsed.hostname != "zenodo.org"
                or parsed.port not in (None, 443)
            ):
                raise ValueError("unapproved_archive_repository_host")
            with self.session.get(
                url,
                headers={
                    "Range": f"bytes={start}-{end}",
                    "Accept-Encoding": "identity",
                    "User-Agent": "GuardianLabAI-public-URL-research/1.0",
                },
                stream=True,
                allow_redirects=False,
                timeout=(15, 60),
            ) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    url = urljoin(url, response.headers["Location"])
                    continue
                if response.status_code != 206:
                    raise ValueError("publisher_does_not_honor_bounded_range")
                expected = f"bytes {start}-{end}/{self.size}"
                if response.headers.get("Content-Range") != expected:
                    raise ValueError("publisher_range_or_object_size_changed")
                if response.headers.get("Content-Encoding", "identity") not in (
                    "",
                    "identity",
                ):
                    raise ValueError("publisher_range_encoding_not_identity")
                tag = response.headers.get("ETag")
                if self.etag is not None and tag != self.etag:
                    raise ValueError("publisher_archive_etag_changed")
                if self.etag is None and tag is not None:
                    self.etag = tag
                result = bytearray()
                for chunk in response.iter_content(65536):
                    result.extend(chunk)
                    if len(result) > size:
                        raise ValueError("publisher_range_exceeded_bound")
            if len(result) != size:
                raise ValueError("publisher_range_incomplete")
            self.position += size
            self.bytes_downloaded += size
            self.requests_made += 1
            return bytes(result)
        raise ValueError("publisher_redirect_limit")


def safe_tabular_members(archive):
    result = []
    for info in archive.infolist():
        if info.filename.lower().endswith((".csv", ".xlsx")):
            if not re.fullmatch(
                r"[A-Za-z0-9 _./()\-]+", info.filename
            ) or ".." in info.filename.split("/"):
                raise ValueError("unexpected_tabular_member_name")
            result.append(
                {
                    "name": info.filename,
                    "bytes": info.file_size,
                    "compressed_bytes": info.compress_size,
                    "crc32": info.CRC,
                }
            )
    return result


def read_pinned_member(archive, specification, max_output=64 * 1024 * 1024):
    info = archive.getinfo(specification["name"])
    if info.flag_bits & 1:
        raise ValueError("encrypted_member_not_supported")
    if (
        info.file_size != specification["bytes"]
        or info.compress_size != specification["compressed_bytes"]
        or info.CRC != specification["crc32"]
    ):
        raise ValueError("archive_member_metadata_changed")
    if info.file_size > max_output or info.compress_size > max_output:
        raise ValueError("archive_member_exceeds_bound")
    with archive.open(info) as stream:
        result = stream.read(max_output + 1)
        if len(result) > max_output or len(result) != info.file_size:
            raise ValueError("archive_member_size_mismatch")
    # ZipExtFile validates CRC when EOF is reached. No path is extracted or executed.
    return result


def open_publisher_archive(asset, session=None):
    handle = PublisherRangeFile(asset["download_url"], asset["bytes"], session=session)
    return handle, zipfile.ZipFile(handle)
