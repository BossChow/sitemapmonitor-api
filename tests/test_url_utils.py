from app.services.url_utils import hash_url, normalize_url


def test_normalize_url_lowercases_host_and_removes_fragment() -> None:
    assert normalize_url("HTTPS://Example.COM:443/path?b=2&a=1#section") == (
        "https://example.com/path?a=1&b=2"
    )


def test_hash_url_is_stable() -> None:
    assert hash_url("https://example.com/") == hash_url("https://example.com/")

