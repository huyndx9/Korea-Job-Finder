"""Safety checks for URLs a user typed into the "add a site" form.

The backend fetches these URLs itself, so without a guard the feature would let
anyone point the server at ``http://localhost:8000`` or a cloud metadata
endpoint and read the response back through the preview. Everything that is not
a plain public http(s) address is rejected.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

ALLOWED_SCHEMES = {"http", "https"}
KEYWORD_PLACEHOLDER = "{keyword}"


class UnsafeUrlError(ValueError):
    """The URL is malformed, non-public, or otherwise not fetchable."""


def _is_public(ip: str) -> bool:
    address = ipaddress.ip_address(ip)
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local      # includes 169.254.169.254 cloud metadata
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def validate_search_url(url: str, *, require_placeholder: bool = True) -> str:
    """Return the URL if it is safe to fetch, else raise UnsafeUrlError."""
    if not url or not url.strip():
        raise UnsafeUrlError("URL is required")
    url = url.strip()

    if require_placeholder and KEYWORD_PLACEHOLDER not in url:
        raise UnsafeUrlError(f"the search URL must contain {KEYWORD_PLACEHOLDER}")

    # resolve against a sample keyword so the placeholder does not break parsing
    parts = urlsplit(url.replace(KEYWORD_PLACEHOLDER, "test"))

    if parts.scheme not in ALLOWED_SCHEMES:
        raise UnsafeUrlError("only http:// and https:// URLs are allowed")
    if parts.username or parts.password:
        raise UnsafeUrlError("credentials in the URL are not allowed")
    if not parts.hostname:
        raise UnsafeUrlError("the URL has no host")

    host = parts.hostname
    try:
        resolved = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"host '{host}' could not be resolved") from exc

    for entry in resolved:
        ip = entry[4][0]
        # note: UnsafeUrlError IS a ValueError, so only the parse is guarded here -
        # wrapping the is_public check too would swallow its specific message
        try:
            public = _is_public(ip)
        except ValueError as exc:
            raise UnsafeUrlError(f"'{host}' resolved to an unusable address ({ip})") from exc
        if not public:
            raise UnsafeUrlError(f"'{host}' resolves to a non-public address ({ip})")

    return url
