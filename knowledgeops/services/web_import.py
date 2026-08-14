"""Safe HTML webpage fetching for knowledge-base imports."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ..rag import ParsedDocument, parse_html_document


class WebImportError(ValueError):
    """Raised when a webpage cannot be safely imported."""


@dataclass(frozen=True)
class WebPageResponse:
    """Fetched webpage bytes and the final validated URL."""

    content: bytes
    url: str
    content_type: str


class _NoRedirectHandler(HTTPRedirectHandler):
    """Expose redirect responses so each destination can be revalidated."""

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


async def import_web_page(
    url: str,
    *,
    max_bytes: int,
    timeout_seconds: float,
) -> ParsedDocument:
    """Fetch a public HTML page and return indexable, normalized text."""
    response = await fetch_web_page(
        url,
        max_bytes=max_bytes,
        timeout_seconds=timeout_seconds,
    )
    if response.content_type not in {"text/html", "application/xhtml+xml"}:
        raise WebImportError("Only HTML webpages can be imported.")

    host = urlsplit(response.url).hostname or "webpage"
    parsed = parse_html_document(response.content, host)
    source_name = parsed.metadata.get("title") or host
    source_name = source_name.strip()[:255] or host
    metadata = {
        **parsed.metadata,
        "source_name": source_name,
        "source_type": "web",
        "source_url": response.url,
    }
    return ParsedDocument(
        text=parsed.text,
        source_name=source_name,
        source_type="web",
        metadata=metadata,
    )


async def fetch_web_page(
    url: str,
    *,
    max_bytes: int,
    timeout_seconds: float,
    max_redirects: int = 3,
) -> WebPageResponse:
    """Fetch a public webpage with bounded redirects, size, and time."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be greater than zero.")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero.")

    current_url = url
    for _ in range(max_redirects + 1):
        await _validate_public_url(current_url)
        result = await asyncio.to_thread(
            _fetch_once,
            current_url,
            max_bytes=max_bytes,
            timeout_seconds=timeout_seconds,
        )
        if isinstance(result, str):
            current_url = urljoin(current_url, result)
            continue
        return result

    raise WebImportError("Webpage redirected too many times.")


async def _validate_public_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise WebImportError("Webpage URL must use HTTP or HTTPS.")
    if not parsed.hostname or parsed.username or parsed.password:
        raise WebImportError("Webpage URL is invalid.")

    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as error:
        raise WebImportError("Webpage URL has an invalid port.") from error

    await asyncio.to_thread(_validate_public_host, parsed.hostname, port)


def _validate_public_host(hostname: str, port: int) -> None:
    """Reject loopback, private, and otherwise non-public destinations."""
    try:
        addresses = socket.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as error:
        raise WebImportError("Webpage host could not be resolved.") from error

    if not addresses:
        raise WebImportError("Webpage host could not be resolved.")

    for address in {entry[4][0] for entry in addresses}:
        parsed_address = ipaddress.ip_address(address)
        if (
            parsed_address.is_private
            or parsed_address.is_loopback
            or parsed_address.is_link_local
            or parsed_address.is_multicast
            or parsed_address.is_reserved
            or parsed_address.is_unspecified
        ):
            raise WebImportError("Webpage URL must resolve to a public address.")


def _fetch_once(
    url: str,
    *,
    max_bytes: int,
    timeout_seconds: float,
) -> WebPageResponse | str:
    opener = build_opener(_NoRedirectHandler())
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "KnowledgeOpsImporter/1.0",
        },
    )

    try:
        response = opener.open(request, timeout=timeout_seconds)
    except HTTPError as error:
        if error.code in {301, 302, 303, 307, 308}:
            location = error.headers.get("Location")
            if location:
                return location
        raise WebImportError(f"Webpage request failed with status {error.code}.") from error
    except URLError as error:
        raise WebImportError("Webpage request failed.") from error

    with response:
        status = getattr(response, "status", response.getcode())
        if status in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location")
            if location:
                return location
            raise WebImportError("Webpage redirect did not include a destination.")
        if status < 200 or status >= 300:
            raise WebImportError(f"Webpage request failed with status {status}.")

        content_type = response.headers.get_content_type().casefold()
        chunks: list[bytes] = []
        total_size = 0
        while chunk := response.read(min(64 * 1024, max_bytes - total_size + 1)):
            total_size += len(chunk)
            if total_size > max_bytes:
                raise WebImportError("Webpage is larger than the import limit.")
            chunks.append(chunk)

        return WebPageResponse(
            content=b"".join(chunks),
            url=response.geturl(),
            content_type=content_type,
        )