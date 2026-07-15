import re
from collections.abc import Iterable
from urllib.parse import urljoin, urlsplit

import httpx

from app.services.http_client import create_sitemap_http_client

COMMON_SITEMAP_PATHS = (
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/wp-sitemap.xml",
)
SITEMAP_DIRECTIVE_PATTERN = re.compile(r"^\s*sitemap\s*:\s*(\S+)\s*$", re.IGNORECASE)


class SitemapDiscovery:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or create_sitemap_http_client()

    def candidates(self, root_url: str) -> list[str]:
        robots_url = urljoin(root_url, "/robots.txt")
        discovered = self._robots_sitemaps(robots_url)
        fallback = [urljoin(root_url, path) for path in COMMON_SITEMAP_PATHS]
        return list(self._unique_http_urls([*discovered, *fallback]))

    def _robots_sitemaps(self, robots_url: str) -> list[str]:
        try:
            response = self.client.get(robots_url)
            response.raise_for_status()
        except httpx.HTTPError:
            return []

        candidates: list[str] = []
        for line in response.text.splitlines():
            directive = SITEMAP_DIRECTIVE_PATTERN.match(line.split("#", maxsplit=1)[0])
            if directive is not None:
                candidates.append(urljoin(robots_url, directive.group(1)))
        return candidates

    @staticmethod
    def _unique_http_urls(urls: Iterable[str]) -> Iterable[str]:
        seen: set[str] = set()
        for url in urls:
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or url in seen:
                continue
            seen.add(url)
            yield url
