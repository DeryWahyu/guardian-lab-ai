"""Bound publisher archive reads and prevent accidental target or whole-file fetches."""

import importlib
import io
import re
import sys
import zipfile

import pytest

from guardian_ml.paths import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
remote = importlib.import_module("v6_remote_zip")
sys.path.pop(0)


class Response:
    def __init__(self, data, start, end, total, status=206, etag="stable"):
        self.status_code = status
        self.headers = {"Content-Range": f"bytes {start}-{end}/{total}", "ETag": etag}
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def iter_content(self, _):
        yield self.data


class Session:
    def __init__(self, content, status=206):
        self.content, self.status, self.calls = content, status, []

    def get(self, url, headers, **kwargs):
        self.calls.append((url, headers))
        start, end = map(int, re.fullmatch(r"bytes=(\d+)-(\d+)", headers["Range"]).groups())
        return Response(self.content[start : end + 1], start, end, len(self.content), self.status)


def archive_bytes():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("data/urls.csv", "url,label\nhttps://example.org/,0\n")
        archive.writestr("images/unused.png", b"unused" * 10000)
    return buffer.getvalue()


def test_ranges_can_read_selected_csv_without_extracting_other_members():
    content = archive_bytes()
    session = Session(content)
    reader, archive = remote.open_publisher_archive(
        {"download_url": "https://zenodo.org/file", "bytes": len(content)}, session
    )
    members = remote.safe_tabular_members(archive)
    assert len(members) == 1
    assert remote.read_pinned_member(archive, members[0]).endswith(b"example.org/,0\n")
    assert all(call[1]["Accept-Encoding"] == "identity" for call in session.calls)
    assert reader.bytes_downloaded < 3000


def test_http_200_is_rejected_before_reading_a_large_full_response():
    session = Session(b"ignored", status=200)
    reader = remote.PublisherRangeFile("https://zenodo.org/file", 4_476_190_126, session=session)
    with pytest.raises(ValueError, match="honor_bounded_range"):
        reader.read(10)


def test_dataset_target_redirect_is_never_requested():
    class RedirectSession:
        def __init__(self):
            self.calls = 0

        def get(self, *_args, **_kwargs):
            self.calls += 1
            result = Response(b"", 0, 0, 10, status=302)
            result.headers["Location"] = "https://example.org/dataset-target"
            return result

    session = RedirectSession()
    reader = remote.PublisherRangeFile("https://zenodo.org/file", 10, session=session)
    with pytest.raises(ValueError, match="unapproved_archive_repository_host"):
        reader.read(1)
    assert session.calls == 1


def test_range_and_memory_bounds_are_enforced_before_reading():
    reader = remote.PublisherRangeFile("https://zenodo.org/file", 100, Session(b"abc"), max_read=8)
    with pytest.raises(ValueError, match="memory_bound"):
        reader.read(9)
    with pytest.raises(ValueError, match="object_size_changed"):
        reader.read(1)


def test_changed_etag_and_member_metadata_are_rejected():
    content = archive_bytes()
    session = Session(content)
    reader, archive = remote.open_publisher_archive(
        {"download_url": "https://zenodo.org/file", "bytes": len(content)}, session
    )
    item = remote.safe_tabular_members(archive)[0]
    with pytest.raises(ValueError, match="metadata_changed"):
        remote.read_pinned_member(archive, {**item, "crc32": 0})
    reader.etag = "changed"
    reader.seek(0)
    with pytest.raises(ValueError, match="etag_changed"):
        reader.read(1)


def test_untrusted_member_paths_are_not_accepted():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../escape.csv", "not extracted")
    with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as archive:
        with pytest.raises(ValueError, match="tabular_member_name"):
            remote.safe_tabular_members(archive)


def test_zip64_offsets_do_not_require_allocating_or_downloading_the_prefix():
    class SparseWriter(io.BytesIO):
        def __init__(self):
            super().__init__()
            self.logical = 2**32 + 100

        def tell(self):
            return self.logical + super().tell()

        def seek(self, offset, whence=0):
            if whence == 0:
                offset -= self.logical
            return self.logical + super().seek(offset, whence)

    sparse = SparseWriter()
    with zipfile.ZipFile(sparse, "w") as archive:
        archive.writestr("urls.csv", "url,label\nhttps://example.net/,1\n")
    tail = sparse.getvalue()
    total = sparse.logical + len(tail)

    class SparseSession:
        def get(self, _url, headers, **_kwargs):
            start, end = map(int, re.fullmatch(r"bytes=(\d+)-(\d+)", headers["Range"]).groups())
            assert start >= sparse.logical
            result = tail[start - sparse.logical : end + 1 - sparse.logical]
            return Response(result, start, end, total)

    reader, archive = remote.open_publisher_archive(
        {"download_url": "https://zenodo.org/file", "bytes": total}, SparseSession()
    )
    item = remote.safe_tabular_members(archive)[0]
    assert b"example.net" in remote.read_pinned_member(archive, item)
    assert reader.bytes_downloaded < 3000
