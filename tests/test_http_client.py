from app.services.http_client import SITEMAP_REQUEST_HEADERS, create_sitemap_http_client


def test_sitemap_http_client_uses_browser_like_headers() -> None:
    with create_sitemap_http_client() as client:
        assert client.headers["User-Agent"] == SITEMAP_REQUEST_HEADERS["User-Agent"]
        assert "Mozilla/5.0" in client.headers["User-Agent"]
        assert client.headers["Accept"] == SITEMAP_REQUEST_HEADERS["Accept"]
        assert client.headers["Accept-Language"] == SITEMAP_REQUEST_HEADERS["Accept-Language"]
