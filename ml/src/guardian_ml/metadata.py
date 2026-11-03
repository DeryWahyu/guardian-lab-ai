"""Checksums and the bundled offline PSL identity for frozen v6 inference."""

import hashlib
from importlib.metadata import version
from pathlib import Path

import tldextract


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def psl_identity():
    snapshot = Path(tldextract.__file__).parent / ".tld_set_snapshot"
    return {
        "package": version("tldextract"),
        "snapshot_sha256": checksum(snapshot),
        "private_suffixes": True,
        "network_refresh": False,
    }
