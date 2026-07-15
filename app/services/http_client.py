import httpx

from app.core.config import settings

SITEMAP_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/xml,text/xml,text/plain,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


def create_sitemap_http_client() -> httpx.Client:
    return httpx.Client(
        timeout=settings.sitemap_fetch_timeout_seconds,
        follow_redirects=True,
        headers=SITEMAP_REQUEST_HEADERS,
    )
