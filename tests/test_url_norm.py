"""URL normalization tests."""
from __future__ import annotations

import pytest

from newsroom.url_norm import normalize_url, url_fingerprint, parse_url


# --- Tracking parameters ---------------------------------------------------

def test_utm_variants_normalize_together():
    a = "https://Example.com/article?id=42&utm_source=twitter&utm_medium=social"
    b = "https://example.com/article?id=42&utm_source=reddit&utm_campaign=fall"
    assert normalize_url(a) == normalize_url(b)


def test_fbclid_removed():
    a = "https://example.com/post/123"
    b = "https://example.com/post/123?fbclid=IwAR1xyz"
    assert normalize_url(a) == normalize_url(b)


def test_gclid_removed():
    a = "https://example.com/?q=hello"
    b = "https://example.com/?q=hello&gclid=abc123"
    assert normalize_url(a) == normalize_url(b)


def test_multiple_tracking_params_removed():
    a = "https://example.com/p/1"
    b = "https://example.com/p/1?fbclid=x&utm_source=twa&mc_cid=88&gclid=zz"
    assert normalize_url(a) == normalize_url(b)


def test_tracking_params_case_insensitive():
    a = "https://example.com/?id=1"
    b = "https://example.com/?id=1&UTM_Source=foo&FBclid=bar"
    assert normalize_url(a) == normalize_url(b)


# --- Fragment ---------------------------------------------------------------

def test_fragment_ignored():
    a = "https://example.com/article"
    b = "https://example.com/article#section-2"
    c = "https://example.com/article#different-fragment"
    assert normalize_url(a) == normalize_url(b) == normalize_url(c)


# --- Meaningful params preserved --------------------------------------------

def test_meaningful_id_param_preserved():
    a = "https://example.com/article"
    b = "https://example.com/article?id=42"
    assert normalize_url(a) != normalize_url(b)


def test_meaningful_query_distinguishes_urls():
    a = "https://example.com/search?q=foo"
    b = "https://example.com/search?q=bar"
    assert normalize_url(a) != normalize_url(b)


def test_query_ordering_normalized():
    a = "https://example.com/?a=1&b=2&c=3"
    b = "https://example.com/?c=3&a=1&b=2"
    assert normalize_url(a) == normalize_url(b)


def test_query_param_case_normalized():
    """Parameter names are case-folded for ordering; values preserved."""
    a = "https://example.com/?A=1&b=2"
    b = "https://example.com/?a=1&B=2"
    assert normalize_url(a) == normalize_url(b)


# --- Host / scheme ---------------------------------------------------------

def test_www_stripped():
    a = "https://www.example.com/article"
    b = "https://example.com/article"
    assert normalize_url(a) == normalize_url(b)


def test_host_lowercased():
    a = "https://EXAMPLE.COM/article"
    b = "https://example.com/article"
    assert normalize_url(a) == normalize_url(b)


def test_default_port_dropped():
    a = "https://example.com:443/article"
    b = "https://example.com/article"
    assert normalize_url(a) == normalize_url(b)
    c = "http://example.com:80/article"
    d = "http://example.com/article"
    assert normalize_url(c) == normalize_url(d)


def test_non_default_port_preserved():
    a = "https://example.com:8080/article"
    assert normalize_url(a) == "https://example.com:8080/article"


def test_scheme_defaulted_to_https_when_missing():
    a = "example.com/article"
    assert normalize_url(a) == "https://example.com/article"


def test_path_trailing_slash_stripped():
    a = "https://example.com/articles/"
    b = "https://example.com/articles"
    assert normalize_url(a) == normalize_url(b)


def test_root_path_keeps_slash():
    a = "https://example.com/"
    assert normalize_url(a) == "https://example.com/"


def test_double_slashes_collapsed():
    a = "https://example.com//foo//bar"
    b = "https://example.com/foo/bar"
    assert normalize_url(a) == normalize_url(b)


# --- Fingerprint -----------------------------------------------------------

def test_fingerprint_equality_for_tracking_variants():
    a = url_fingerprint("https://example.com/article?id=1&utm_source=x")
    b = url_fingerprint("https://example.com/article?id=1")
    assert a == b


def test_fingerprint_distinct_for_different_meaningful_urls():
    a = url_fingerprint("https://example.com/article?id=1")
    b = url_fingerprint("https://example.com/article?id=2")
    assert a != b


def test_fingerprint_stable_across_runs():
    a = url_fingerprint("https://example.com/article?id=1")
    b = url_fingerprint("https://example.com/article?id=1")
    assert a == b
    assert len(a) == 16


def test_fingerprint_strict_format():
    fp = url_fingerprint("https://example.com/path")
    assert isinstance(fp, str)
    assert len(fp) == 16
    assert all(c in "0123456789abcdef" for c in fp)


# --- Parse helper ----------------------------------------------------------

def test_parse_url_returns_fields():
    out = parse_url("https://example.com/article?utm_source=x")
    assert out["canonical_url"] == "https://example.com/article"
    assert out["domain"] == "example.com"
    assert len(out["fp_url"]) == 16
    assert len(out["fp_domain"]) == 16


# --- Edge cases ------------------------------------------------------------

def test_empty_url_raises():
    with pytest.raises(ValueError):
        normalize_url("")


def test_non_string_input_raises():
    with pytest.raises(ValueError):
        normalize_url(None)  # type: ignore


def test_oversized_url_raises():
    with pytest.raises(ValueError):
        normalize_url("https://example.com/" + "a" * 3000)


def test_unicode_url_preserved():
    a = "https://example.com/路径"
    assert normalize_url(a) == "https://example.com/%E8%B7%AF%E5%BE%84"


def test_unsupported_scheme_preserved():
    """ftp/magnet/etc. are passed through without breaking the parser."""
    a = "magnet:?xt=urn:btih:abc"
    out = normalize_url(a)
    assert out.startswith("magnet:")
