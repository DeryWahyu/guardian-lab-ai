"""Bounded reads of ZIP text members; never download or execute target content."""

import struct
import zlib

MAX_MEMBER_BYTES = 65536
MAX_RANGE_BYTES = 131072


def decode_member(data, info):
    if len(data) < 30:
        raise ValueError("truncated_zip_header")
    header = struct.unpack("<4s5H3I2H", data[:30])
    if header[0] != b"PK\x03\x04" or header[2] & 1:
        raise ValueError("unsupported_zip_header")
    if header[3] != info.compress_type or info.compress_type not in (0, 8):
        raise ValueError("unsupported_zip_compression")
    offset = 30 + header[9] + header[10]
    if offset + info.compress_size > len(data):
        raise ValueError("truncated_zip_member")
    encoding = "utf-8" if header[2] & 0x800 else "cp437"
    if data[30 : 30 + header[9]].decode(encoding) != info.filename:
        raise ValueError("zip_member_identity_mismatch")
    compressed = data[offset : offset + info.compress_size]
    if info.file_size > MAX_MEMBER_BYTES:
        raise ValueError("zip_member_too_large")
    if info.compress_type == 8:
        decoder = zlib.decompressobj(-15)
        try:
            raw = decoder.decompress(compressed, MAX_MEMBER_BYTES + 1)
        except zlib.error:
            raise ValueError("invalid_zip_stream") from None
        if not decoder.eof or decoder.unused_data:
            raise ValueError("invalid_or_oversized_zip_stream")
    else:
        raw = compressed
    if len(raw) != info.file_size or len(raw) > MAX_MEMBER_BYTES:
        raise ValueError("zip_member_size_mismatch")
    if zlib.crc32(raw) & 0xFFFFFFFF != info.CRC:
        raise ValueError("zip_crc_mismatch")
    return raw


def fetch_member(session, url, info, archive_size):
    amount = 30 + len(info.filename.encode("utf-8")) + len(info.extra) + info.compress_size + 1024
    if amount > MAX_RANGE_BYTES or info.file_size > MAX_MEMBER_BYTES:
        raise ValueError("zip_member_range_too_large")
    start = info.header_offset
    end = min(start + amount - 1, archive_size - 1)
    with session.get(
        url, headers={"Range": f"bytes={start}-{end}"}, timeout=(20, 45), stream=True
    ) as response:
        response.raise_for_status()
        if response.status_code != 206:
            raise ValueError("dataset_server_range_not_honored")
        if response.headers.get("Content-Range") != f"bytes {start}-{end}/{archive_size}":
            raise ValueError("dataset_range_identity_mismatch")
        data = response.raw.read(end - start + 2)
    if len(data) != end - start + 1:
        raise ValueError("dataset_range_length_mismatch")
    return decode_member(data, info)
