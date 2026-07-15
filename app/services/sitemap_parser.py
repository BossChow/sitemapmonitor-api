from dataclasses import dataclass
from gzip import BadGzipFile, decompress

import httpx
from lxml import etree

from app.core.config import settings
from app.services.http_client import create_sitemap_http_client
from app.services.url_utils import normalize_url


@dataclass(frozen=True)
class SitemapEntry:
    url: str
    lastmod: str | None


class SitemapFetchError(Exception):
    pass


class SitemapParser:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or create_sitemap_http_client()

    def collect(self, sitemap_url: str) -> list[SitemapEntry]:
        entries: list[SitemapEntry] = []
        visited: set[str] = set()
        self._collect_recursive(sitemap_url, entries, visited, depth=0)
        return entries

    def _collect_recursive(
        self,
        sitemap_url: str,
        entries: list[SitemapEntry],
        visited: set[str],
        depth: int,
    ) -> None:
        if depth > settings.max_sitemap_depth:
            raise SitemapFetchError("Maximum sitemap index depth exceeded")
        if len(visited) >= settings.max_sitemap_files:
            raise SitemapFetchError("Maximum sitemap file count exceeded")

        normalized_sitemap_url = normalize_url(sitemap_url)
        if normalized_sitemap_url in visited:
            return

        visited.add(normalized_sitemap_url)
        content = self._fetch(normalized_sitemap_url)
        parser = etree.XMLParser(resolve_entities=False, no_network=True)
        root = etree.fromstring(content, parser=parser)
        local_name = etree.QName(root).localname

        if local_name == "sitemapindex":
            for loc in root.xpath("//*[local-name()='sitemap']/*[local-name()='loc']/text()"):
                self._collect_recursive(str(loc), entries, visited, depth + 1)
            return

        if local_name != "urlset":
            raise SitemapFetchError(f"Unsupported sitemap root element: {local_name}")

        for url_node in root.xpath("//*[local-name()='url']"):
            loc_values = url_node.xpath("./*[local-name()='loc']/text()")
            if not loc_values:
                continue
            lastmod_values = url_node.xpath("./*[local-name()='lastmod']/text()")
            entries.append(
                SitemapEntry(
                    url=normalize_url(str(loc_values[0])),
                    lastmod=str(lastmod_values[0]).strip() if lastmod_values else None,
                )
            )

    def _fetch(self, sitemap_url: str) -> bytes:
        try:
            response = self.client.get(sitemap_url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise SitemapFetchError(f"Failed to fetch sitemap {sitemap_url}: {exc}") from exc

        content = response.content
        if sitemap_url.endswith(".gz"):
            try:
                return decompress(content)
            except BadGzipFile as exc:
                raise SitemapFetchError(f"Invalid gzip sitemap {sitemap_url}") from exc
        return content
