import httpx

from app.services.sitemap_discovery import SitemapDiscovery


def test_discovery_uses_robots_sitemaps_before_common_paths() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://example.com/robots.txt"
        return httpx.Response(
            200,
            text="""
                User-agent: *
                Sitemap: https://example.com/custom.xml
                sitemap: /secondary.xml # extra sitemap
            """,
        )

    discovery = SitemapDiscovery(httpx.Client(transport=httpx.MockTransport(handler)))

    assert discovery.candidates("https://example.com") == [
        "https://example.com/custom.xml",
        "https://example.com/secondary.xml",
        "https://example.com/sitemap.xml",
        "https://example.com/sitemap_index.xml",
        "https://example.com/sitemap-index.xml",
        "https://example.com/wp-sitemap.xml",
    ]


def test_discovery_falls_back_to_common_paths_when_robots_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    discovery = SitemapDiscovery(httpx.Client(transport=httpx.MockTransport(handler)))

    assert discovery.candidates("https://example.com") == [
        "https://example.com/sitemap.xml",
        "https://example.com/sitemap_index.xml",
        "https://example.com/sitemap-index.xml",
        "https://example.com/wp-sitemap.xml",
    ]
