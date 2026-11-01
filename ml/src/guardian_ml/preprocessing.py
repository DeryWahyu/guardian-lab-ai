"""Single offline representation shared by ingestion, training, and prediction.

Regex screening is conservative, not a proof of complete anonymization. No raw
URLs, queries, fragments, userinfo, or request strings are logged or persisted.
"""

from __future__ import annotations

import hashlib
import ipaddress
import re
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import quote, unquote, urlsplit

import tldextract

EXTRACT = tldextract.TLDExtract(
    suffix_list_urls=(),
    cache_dir=None,
    include_psl_private_domains=True,
)
EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}")
PHONE = re.compile(r"(?<!\w)(?:\+62|62|0)[ .-]?8[1-9](?:[ .-]?\d){6,10}\b")
NUMBER = re.compile(r"(?<!\d)(?:\d[ -]?){8,}(?!\d)")
TOKEN = re.compile(
    r"\d{9,10}:[\w-]{30,}|[a-fA-F0-9]{24,}|"
    r"[A-Za-z0-9_-]{24,}\.[A-Za-z0-9_-]{16,}(?:\.[A-Za-z0-9_-]+)?|"
    r"(?=[A-Za-z0-9_-]{24,}(?:\W|$))(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{24,}"
)
SENSITIVE_KEY = re.compile(
    r"^(?:password|passwd|pwd|token|secret|otp|pin|session|authorization|"
    r"email|phone|mobile|nik|account|credential|access_token|api_key)$",
    re.I,
)
CONTROL = re.compile(r"[\x00-\x20\x7f\\]")
HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.I)


class InvalidUrl(ValueError):
    """Only a fixed reason code; never include user input in the exception."""


@dataclass(frozen=True)
class PreparedUrl:
    core: str
    host: str
    path: str
    scheme: str
    group: str
    suffix: str
    redactions: int

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.core.encode()).hexdigest()


@lru_cache(maxsize=100_000)
def domain_parts(host: str) -> tuple[str, str]:
    result = EXTRACT(host)
    return result.top_domain_under_public_suffix or host, result.suffix or "unknown"


def redact_path(path: str) -> tuple[str, int]:
    decoded = unquote(unquote(path))
    if CONTROL.search(decoded.replace(" ", "")):
        raise InvalidUrl("decoded_control_or_backslash")
    if re.search(r"%[0-9a-fA-F]{2}", decoded):
        raise InvalidUrl("ambiguous_nested_encoding")
    count = 0
    # A replacement can join surrounding token pieces into a new match.
    for _ in range(5):
        changed = 0
        for pattern in (EMAIL, PHONE, NUMBER, TOKEN):
            decoded, matches = pattern.subn("REDACTED", decoded)
            count += matches
            changed += matches
        if not changed:
            break
    segments = decoded.split("/")
    for index in range(1, len(segments)):
        if SENSITIVE_KEY.fullmatch(segments[index - 1]) and segments[index]:
            segments[index] = "REDACTED"
            count += 1
    # Fixed escaping avoids storing decoded data as a new query/fragment.
    encoded = quote("/".join(segments), safe="/-._~!$&'()*+,;=:@")
    if any(pattern.search(encoded) for pattern in (EMAIL, PHONE, NUMBER, TOKEN)):
        raise InvalidUrl("residual_sensitive_candidate")
    return encoded, count


def prepare_url(value: str) -> PreparedUrl:
    if not isinstance(value, str) or not value.strip():
        raise InvalidUrl("empty")
    value = value.strip()
    if len(value) > 16_384:
        raise InvalidUrl("too_long")
    if CONTROL.search(value):
        raise InvalidUrl("control_whitespace_or_backslash")
    if "://" not in value:
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value) and not re.match(
            r"^[^/:]+:\d+(?:/|$)",
            value,
        ):
            raise InvalidUrl("unsupported_scheme")
        value = "https://" + value
    try:
        parsed = urlsplit(value)
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            raise InvalidUrl("unsupported_scheme")
        if parsed.username is not None or parsed.password is not None:
            raise InvalidUrl("userinfo")
        host = (parsed.hostname or "").rstrip(".").encode("idna").decode("ascii").lower()
        port = parsed.port
    except (ValueError, UnicodeError):
        raise InvalidUrl("invalid_authority") from None
    if not host or len(host) > 253:
        raise InvalidUrl("invalid_host")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None:
        if not address.is_global:
            raise InvalidUrl("non_public_ip")
    elif "." not in host or not all(HOST_LABEL.fullmatch(part) for part in host.split(".")):
        raise InvalidUrl("invalid_or_local_host")
    elif host.endswith((".localhost", ".local", ".internal", ".test", ".invalid")):
        raise InvalidUrl("non_public_host")
    if PHONE.search(host) or NUMBER.search(host) or TOKEN.search(host):
        raise InvalidUrl("sensitive_host_candidate")
    group, suffix = domain_parts(host)
    if address is not None:
        group, suffix = host, "ip"
    authority = f"[{host}]" if ":" in host else host
    if port is not None and (scheme, port) not in (("http", 80), ("https", 443)):
        authority += f":{port}"
    path, count = redact_path(parsed.path or "/")
    return PreparedUrl(f"{scheme}://{authority}{path}", host, path, scheme, group, suffix, count)
