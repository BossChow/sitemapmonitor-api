import httpx

from app.services.sitemap_parser import SitemapParser


def test_parser_collects_urlset_entries() -> None:
    xml = b"""
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url>
        <loc>HTTPS://Example.COM/b?z=1&amp;a=2#section</loc>
        <lastmod>2026-07-12</lastmod>
      </url>
    </urlset>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=xml)

    parser = SitemapParser(httpx.Client(transport=httpx.MockTransport(handler)))
    entries = parser.collect("https://example.com/sitemap.xml")

    assert len(entries) == 1
    assert entries[0].url == "HTTPS://Example.COM/b?z=1&a=2#section"
    assert entries[0].lastmod == "2026-07-12"


def test_parser_follows_sitemap_index() -> None:
    index_xml = b"""
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://example.com/nested.xml</loc></sitemap>
    </sitemapindex>
    """
    nested_xml = b"""
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/a</loc></url>
    </urlset>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        content = nested_xml if str(request.url).endswith("/nested.xml") else index_xml
        return httpx.Response(200, content=content)

    parser = SitemapParser(httpx.Client(transport=httpx.MockTransport(handler)))
    entries = parser.collect("https://example.com/sitemap.xml")

    assert [entry.url for entry in entries] == ["https://example.com/a"]
