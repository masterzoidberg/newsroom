"""Canonical URL normalization.

Per BUILD_PLAN §8.0:
- lowercase scheme + host
- default https
- drop default ports (443/80)
- strip leading `www.`
- drop fragment
- remove known tracking parameters (case-insensitive, configurable)
- keep all other params
- collapse duplicate `/`
- strip trailing `/` (except root)
- sort remaining params by name
- return `(canonical_url, fp_url)` where fp_url = sha256(host|path|sorted_query)[:16]

This is the foundation for Stage-1 exact source identity. The fingerprint
is intentionally an equality hash (captures physical source identity, not
semantic similarity), but normalization is what prevents trivial tracking-
parameter drift from producing different URLs.

Path encoding:
- Existing valid percent-encoded sequences are preserved (a literal `%`
  followed by two hex digits is not re-encoded into `%25`).
- Literal Unicode characters in the path are encoded to UTF-8 percent form.
- Implementation: `unquote(path) -> quote(..., safe="/:")`. This is
  idempotent for already-encoded paths and round-trips literal Unicode.
"""
from __future__ import annotations

import hashlib
import re
from typing import Iterable
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlparse, urlunparse


# Default tracking parameters known to be safe to strip. Operators may extend
# this list; unknown-but-meaningful parameters are preserved.
DEFAULT_TRACKING_PARAMS: frozenset[str] = frozenset({
    # Google / Urchin
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_name", "utm_brand", "utm_social", "utm_creative_format",
    # Facebook / Meta
    "fbclid", "fb_action_ids", "fb_action_types", "fb_ref", "fb_source",
    # Google ads
    "gclid", "gclsrc", "dclid", "gbraid", "wbraid",
    # Mailchimp / email
    "mc_cid", "mc_eid",
    # Instagram
    "igshid", "igsh",
    # Referrer-style
    "ref_src", "ref_url", "ref",
    # Outbrain / Taboola
    "oborigurl", "oly_enc_id", "oly_anon_id", "oly_anon_id_old",
    # HubSpot misc
    "_hsenc", "_hsmi", "__hsfp", "__hsf", "__hssc",
    # Vero
    "vero_id", "vero_conv",
    # Misc
    "yclid", "msclkid", "twclid", "ttclid", "li_fat_id", "scid",
})


_DEFAULT_PORT = {"http": 80, "https": 443}


def _strip_tracking(qs_pairs: list[tuple[str, str]], tracking: Iterable[str]) -> list[tuple[str, str]]:
    tracking = {t.lower() for t in tracking}
    return [(k, v) for k, v in qs_pairs if k.lower() not in tracking]


def _looks_like_schemeless(raw: str) -> bool:
    """True when the URL has no scheme but could be parsed as http(s).

    Distinguishes `example.com/article` from `magnet:?xt=urn:btih:abc`:
    we only auto-prefix http/https when the first segment looks like a
    hostname (no `:` before the first `/`).
    """
    if "://" in raw:
        return False
    head = raw.split("/", 1)[0]
    return ":" not in head


def _normalize_path(path: str) -> str:
    """Collapse duplicate slashes, strip trailing slash (except root),
    and round-trip encoding so literal Unicode is percent-encoded and
    existing valid percent escapes are preserved (NOT double-encoded).

    A "valid percent escape" is `%XX` where XX is two hex digits. The
    round-trip is: unquote (decodes valid escapes, leaves malformed
    ones as-is) then re-quote with a permissive safe set (`/` and `:`).
    Both literal Unicode and pre-encoded paths converge to the same
    canonical form.
    """
    if not path:
        return path
    # Collapse duplicate slashes first.
    path = re.sub(r"/+", "/", path)
    # unquote leaves already-encoded sequences intact conceptually
    # (they decode to their byte representation, then re-quote encodes
    # any literal non-ASCII back to UTF-8 percent form).
    try:
        decoded = unquote(path)
    except Exception:
        decoded = path
    # Re-quote: safe='/:' preserves path separators and a single colon
    # which is common in URL paths (e.g. /2024/01:title).
    canonical = quote(decoded, safe="/:")
    # Strip trailing slash except at root.
    if len(canonical) > 1 and canonical.endswith("/"):
        canonical = canonical[:-1]
    return canonical


def normalize_url(
    url: str,
    *,
    tracking: Iterable[str] | None = None,
    max_length: int = 2048,
) -> str:
    """Return a canonical URL string. Raises ValueError on unparseable input.

    Pass-through semantics for non-HTTP schemes: `magnet:`, `mailto:`,
    `ftp:`, etc. are returned unchanged after a basic whitespace strip.
    """
    if not isinstance(url, str):
        raise ValueError("url must be a string")
    raw = url.strip()
    if not raw:
        raise ValueError("url is empty")
    if len(raw) > max_length:
        raise ValueError(f"url exceeds max length {max_length}")

    # Coerce schemeless http-style input to https:// so urlparse doesn't
    # misread the host as the path. Non-http schemes pass through.
    if _looks_like_schemeless(raw):
        raw = f"https://{raw}"
    parsed = urlparse(raw)

    # Scheme: lowercase. If unsupported, return stripped input as-is.
    scheme = (parsed.scheme or "https").lower()
    if scheme not in ("http", "https"):
        return raw

    # Host: lowercase, strip leading www.
    try:
        host = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"invalid URL host or port: {exc}") from exc
    if not host:
        raise ValueError("HTTP(S) URL must include a host")
    if any(ch.isspace() for ch in host):
        raise ValueError("HTTP(S) URL host must not contain whitespace")
    if host.startswith("www."):
        host = host[4:]

    # Port: drop if default for the scheme.
    if port is not None and port == _DEFAULT_PORT.get(scheme):
        port = None
    netloc = host if port is None else f"{host}:{port}"

    # Path: normalize encoding, collapse slashes, strip trailing slash.
    path = _normalize_path(parsed.path or "")

    # Query: drop tracking params, lowercase names, sort, keep all others.
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    pairs = _strip_tracking(pairs, tracking or DEFAULT_TRACKING_PARAMS)
    pairs = [(k.lower(), v) for k, v in pairs]
    pairs.sort(key=lambda kv: (kv[0], kv[1]))
    query = urlencode(pairs, doseq=True, quote_via=quote)

    # Fragment: dropped.
    return urlunparse((scheme, netloc, path, "", query, ""))


def url_fingerprint(url: str, *, tracking: Iterable[str] | None = None) -> str:
    """Return a deterministic 16-char fingerprint for the canonicalized URL.

    Identity-only — equality is correct here because it captures physical
    source identity, not semantic similarity.
    """
    canonical = normalize_url(url, tracking=tracking)
    parsed = urlparse(canonical)
    basis = f"{parsed.scheme}|{parsed.hostname}|{parsed.port or ''}|{parsed.path}|{parsed.query}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def parse_url(url: str) -> dict[str, str]:
    """Return a small dict of useful normalized fields.

    Includes:
        canonical_url, domain, fp_url, fp_domain
    """
    canonical = normalize_url(url)
    parsed = urlparse(canonical)
    domain = parsed.hostname or ""
    return {
        "canonical_url": canonical,
        "domain": domain,
        "fp_url": url_fingerprint(url),
        "fp_domain": hashlib.sha256(domain.encode("utf-8")).hexdigest()[:16],
    }
