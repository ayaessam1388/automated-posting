"""Message and CTA-link validation rules."""

import ipaddress
import re
from urllib.parse import urlsplit

MAX_MESSAGE_LENGTH = 200

# Anything that looks like a link: explicit http(s) URLs and bare "www." links.
_LINK_PATTERN = re.compile(r"(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)
# Punctuation that usually ends a sentence rather than belonging to the URL.
_TRAILING_PUNCTUATION = ".,;:!?)]}'\""
_DOMAIN_PATTERN = re.compile(
    r"^(?=.{1,253}$)"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})$"
)


def find_links(text: str) -> list[str]:
    """Return every link-like substring in `text`, without trailing punctuation."""
    return [match.group().rstrip(_TRAILING_PUNCTUATION) for match in _LINK_PATTERN.finditer(text)]


def validate_url(url: str) -> None:
    """Raise ValueError if `url` is not a public http(s) URL with a valid domain."""
    if url.lower().startswith("www."):
        raise ValueError(f"CTA link '{url}' must start with http:// or https://.")

    parts = urlsplit(url)
    if parts.scheme.lower() not in {"http", "https"}:
        raise ValueError(f"CTA link '{url}' must use http or https.")

    host = parts.hostname
    if not host:
        raise ValueError(f"CTA link '{url}' has no domain name.")

    try:
        parts.port  # noqa: B018 - raises ValueError for an invalid port
    except ValueError:
        raise ValueError(f"CTA link '{url}' has an invalid port.") from None

    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError(f"CTA link '{url}' must use a domain name, not an IP address.")

    try:
        ascii_host = host.encode("idna").decode("ascii")
    except UnicodeError:
        raise ValueError(f"CTA link '{url}' has an invalid domain name.") from None

    if not _DOMAIN_PATTERN.match(ascii_host):
        raise ValueError(f"CTA link '{url}' has an invalid domain name.")


def extract_single_link(message: str) -> str:
    """Return the message's only CTA link, or raise ValueError explaining what is wrong."""
    links = find_links(message)
    if not links:
        raise ValueError("Message must include exactly one CTA link (http:// or https://); none found.")
    if len(links) > 1:
        raise ValueError(f"Message must include exactly one CTA link; found {len(links)}: {', '.join(links)}.")
    validate_url(links[0])
    return links[0]


def validate_message(message: str) -> str:
    """Normalise and validate a posting message; return the cleaned text."""
    message = message.strip()
    if not message:
        raise ValueError("Message must not be empty.")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise ValueError(
            f"Message must not exceed {MAX_MESSAGE_LENGTH} characters (got {len(message)})."
        )
    extract_single_link(message)
    return message
