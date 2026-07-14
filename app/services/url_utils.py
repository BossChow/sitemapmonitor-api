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
    return sha256(url.encode("utf-8")).hexdigest()

