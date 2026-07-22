"""Fetchable helper endpoints for the site_audit SOP.

Chat clients can't read raw HTML (their fetch strips scripts/meta) or call the
Places API — but they CAN fetch plain URLs. These helpers back /check/* HTTP
routes: the client-side Claude fetches them like any web page and gets clean
JSON facts. No LLM calls, no MCP tool-list changes (tool surface stays frozen).
"""

import ipaddress
import json
import os
import re
import socket
from urllib.parse import urlparse

import httpx

_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/126.0 Safari/537.36")
_MAX_BYTES = 2_000_000


def _host_is_private(hostname: str) -> bool:
    """SSRF guard: refuse to fetch anything resolving to a private/local address."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return True
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    return False


async def _fetch_raw(url: str) -> tuple[str, str, int]:
    """Fetch raw HTML with guards. Returns (final_url, html, status)."""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Only http(s) URLs are supported.")
    if _host_is_private(parsed.hostname):
        raise ValueError("Host not allowed.")
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=15, headers={"User-Agent": _UA}
    ) as client:
        r = await client.get(parsed.geturl())
        return str(r.url), r.text[:_MAX_BYTES], r.status_code


def _strip_tags(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()


async def analyze_site(url: str) -> dict:
    """Raw-HTML facts a markdown-converting fetch cannot see."""
    final_url, html, status = await _fetch_raw(url)

    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    metadesc = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', html, re.S | re.I
    ) or re.search(
        r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']', html, re.S | re.I
    )
    h1s = [_strip_tags(m) for m in re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)][:5]

    ld_blocks = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.S | re.I
    )
    schema_types: list = []
    for block in ld_blocks:
        try:
            data = json.loads(block.strip())
        except ValueError:
            schema_types.append("UNPARSEABLE_JSON_LD")
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict):
                t = item.get("@type", "unknown")
                schema_types.append(t if isinstance(t, str) else list(t))

    return {
        "url": final_url,
        "http_status": status,
        "https": final_url.startswith("https://"),
        "title": _strip_tags(title.group(1)) if title else None,
        "meta_description": _strip_tags(metadesc.group(1)) if metadesc else None,
        "h1": h1s,
        "json_ld_blocks": len(ld_blocks),
        "schema_types": schema_types,
        "viewport_meta": bool(re.search(r'<meta[^>]+name=["\']viewport["\']', html, re.I)),
        "tel_links": sorted(set(re.findall(r'href=["\']tel:([^"\']+)["\']', html, re.I)))[:5],
        "map_embed": bool(re.search(
            r"google\.com/maps/embed|maps\.googleapis\.com|<iframe[^>]+maps", html, re.I)),
        "note": "Facts extracted from raw HTML — includes what markdown fetches strip.",
    }


_PLACES_SEARCH = "https://places.googleapis.com/v1/places:searchText"
_SEARCH_FIELDS = ",".join(f"places.{f}" for f in (
    "id", "displayName", "formattedAddress", "rating", "userRatingCount",
    "primaryTypeDisplayName", "businessStatus", "websiteUri",
    "nationalPhoneNumber", "regularOpeningHours.weekdayDescriptions", "photos.name",
))


async def gbp_lookup(query: str) -> dict:
    """Rating/review facts from the official Places API. Needs GOOGLE_PLACES_API_KEY."""
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
    if not api_key:
        return {
            "error": "GBP lookup not configured on the server yet.",
            "hint": "Falls back to manual: check the listing on Google Maps and report "
                    "rating, review count, and recency by hand.",
        }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            _PLACES_SEARCH,
            json={"textQuery": query, "maxResultCount": 3},
            headers={"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": _SEARCH_FIELDS},
        )
        if r.status_code != 200:
            return {"error": f"Places API error {r.status_code}", "detail": r.text[:300]}
        places = r.json().get("places", [])

        results = []
        for i, p in enumerate(places):
            entry = {
                "name": (p.get("displayName") or {}).get("text"),
                "address": p.get("formattedAddress"),
                "rating": p.get("rating"),
                "review_count": p.get("userRatingCount"),
                "primary_category": p.get("primaryTypeDisplayName", {}).get("text")
                    if isinstance(p.get("primaryTypeDisplayName"), dict)
                    else p.get("primaryTypeDisplayName"),
                "business_status": p.get("businessStatus"),
                "website": p.get("websiteUri"),
                "phone": p.get("nationalPhoneNumber"),
                "hours_listed": bool((p.get("regularOpeningHours") or {}).get("weekdayDescriptions")),
                "photo_count_sample": len(p.get("photos", []) or []),
            }
            # newest visible review for the top match only (extra API call)
            if i == 0 and p.get("id"):
                d = await client.get(
                    f"https://places.googleapis.com/v1/places/{p['id']}",
                    headers={"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": "reviews"},
                )
                if d.status_code == 200:
                    reviews = d.json().get("reviews", []) or []
                    times = sorted((rv.get("publishTime", "") for rv in reviews), reverse=True)
                    entry["newest_visible_review"] = times[0] if times else None
                    entry["visible_reviews_note"] = (
                        "publishTime of newest among the ~5 reviews the API exposes — "
                        "an approximation of recency, not the full history"
                    )
            results.append(entry)

    return {"query": query, "matches": results,
            "note": "Official Google Places data. Owner-response rate is not exposed "
                    "by the API — check manually on the listing."}
