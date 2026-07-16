from datetime import UTC, datetime

from app.services.url_utils import hash_url, normalize_url, parse_sitemap_lastmod


def test_normalize_url_lowercases_host_and_removes_fragment() -> None:
    assert normalize_url("HTTPS://Example.COM:443/path?b=2&a=1#section") == (
        "https://example.com/path?a=1&b=2"
    )


def test_hash_url_is_stable() -> None:
    assert hash_url("https://example.com/") == hash_url("https://example.com/")


def test_hash_url_normalizes_before_hashing() -> None:
    assert hash_url("HTTPS://Example.COM:443/path?b=2&a=1#section") == hash_url(
        "https://example.com/path?a=1&b=2"
    )


def test_parse_sitemap_lastmod_supports_date_and_datetime() -> None:
    assert parse_sitemap_lastmod("2026-07-13") == datetime(2026, 7, 13, tzinfo=UTC)
    assert parse_sitemap_lastmod("2026-07-13T08:30:00+08:00") == datetime(
        2026,
        7,
        13,
        0,
        30,
        tzinfo=UTC,
    )
