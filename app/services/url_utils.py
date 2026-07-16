from datetime import UTC, date, datetime
from hashlib import sha256
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    hostname = parts.hostname.lower() if parts.hostname else ""
    port = f":{parts.port}" if parts.port else ""

    if (scheme == "http" and parts.port == 80) or (scheme == "https" and parts.port == 443):
        port = ""

    path = parts.path or "/"
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return urlunsplit((scheme, f"{hostname}{port}", path, query, ""))


def hash_url(url: str) -> str:
    return sha256(normalize_url(url).encode("utf-8")).hexdigest()


def parse_sitemap_lastmod(lastmod: str | None) -> datetime | None:
    if lastmod is None:
        return None

    value = lastmod.strip()
    if not value:
        return None

    try:
        if "T" not in value and " " not in value:
            return datetime.combine(date.fromisoformat(value), datetime.min.time(), tzinfo=UTC)

        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except ValueError:
        return None


def derive_site_name(root_url: str) -> str:
    hostname = urlsplit(root_url).hostname or ""
    hostname = hostname.removeprefix("www.")
    label = hostname.split(".", maxsplit=1)[0]
    return label[:1].upper() + label[1:]
