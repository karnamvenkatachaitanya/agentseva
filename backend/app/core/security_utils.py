"""Security helpers — HTTPS URL validation for outbound payment links.

Production policy: any customer-facing redirect URL (Razorpay payment links,
callbacks) must be served over **HTTPS**. These helpers enforce that so an
accidental ``http://`` link never reaches a customer.
"""

from __future__ import annotations

from urllib.parse import urlparse


def is_https_url(url: str) -> bool:
    """Return ``True`` if ``url`` is a well-formed ``https://`` URL."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
    except (ValueError, TypeError):
        return False
    return parsed.scheme == "https" and bool(parsed.netloc)


def assert_https(url: str, *, field: str = "url") -> str:
    """Return ``url`` if it is HTTPS, else raise ``ValueError``."""
    if not is_https_url(url):
        raise ValueError(f"{field} must be a secure https:// URL, got: {url!r}")
    return url


def request_is_https(scheme: str, forwarded_proto: str | None = None) -> bool:
    """Determine whether the *effective* request scheme is HTTPS.

    Honours a proxy-provided ``X-Forwarded-Proto`` header (set by Cloudflare /
    nginx / a load balancer) which takes precedence over the raw scheme once
    ``ProxyHeadersMiddleware`` has processed it.
    """
    effective = (forwarded_proto or scheme or "").split(",")[0].strip().lower()
    return effective == "https"
