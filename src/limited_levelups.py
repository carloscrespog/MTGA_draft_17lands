"""Discover tier-list IDs from the current Limited Level-Ups website."""

import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import requests


LLU_ORIGIN = "https://limitedlevelups.com"
TIER_URL_LLU = f"{LLU_ORIGIN}/api/tier-list/"
LLU_HEADERS = {
    "accept": "*/*",
    "cache-control": "no-cache",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
    ),
}


def normalize_set_code(set_code: str) -> str:
    code = set_code.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{2,10}", code):
        raise ValueError("Enter a valid set code for Limited Level-Ups")
    return code


def llu_headers(set_code: str) -> dict:
    return {**LLU_HEADERS, "referer": f"{LLU_ORIGIN}/tier-list/{set_code}"}


class _ModuleScripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("type") == "module" and attrs.get("src"):
            self.sources.append(attrs["src"])


def _array_literal(source: str, start: int) -> str:
    """Read an array without evaluating JavaScript or ending at a quoted ']'."""
    depth = 0
    quote = None
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in "\"'`":
            quote = char
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise ValueError("Incomplete tier-list configuration in LLU JavaScript")


def _ids_from_bundle(source: str, set_code: str):
    """Read single-list and per-grader mappings, regardless of variable names."""
    key = rf"(?:\b{re.escape(set_code)}\b|\"{re.escape(set_code)}\"|'{re.escape(set_code)}')"
    entries = re.finditer(rf"(?:^|[{{,])\s*{key}\s*:\s*", source)
    single_ids, grader_ids = [], []
    for entry in entries:
        value = source[entry.end():]
        single = re.match(r"([\"'])([a-fA-F0-9]{32})\1", value)
        if single:
            single_ids.append(single.group(2).lower())
        elif value.startswith("["):
            array = _array_literal(source, entry.end())
            grader_ids.extend(match.group(2).lower() for match in re.finditer(
                r"(?:\buid\b|\"uid\"|'uid')\s*:\s*([\"'])([a-fA-F0-9]{32})\1", array
            ))
    return single_ids, grader_ids


def discover_tier_list_ids(set_code: str) -> list[str]:
    """Follow the set page's current module assets to its published tier lists."""
    set_code = normalize_set_code(set_code)
    page_url = f"{LLU_ORIGIN}/tier-list/{set_code}"
    headers = llu_headers(set_code)
    response = requests.get(page_url, headers=headers, timeout=10)
    response.raise_for_status()
    parser = _ModuleScripts()
    parser.feed(response.text)
    assets = list(dict.fromkeys(
        urljoin(page_url, source) for source in parser.sources
        if urlsplit(urljoin(page_url, source)).netloc == urlsplit(LLU_ORIGIN).netloc
        and urlsplit(urljoin(page_url, source)).scheme == "https"
    ))
    if not assets:
        raise ValueError("No JavaScript modules found on the Limited Level-Ups set page")

    single_ids, grader_ids = [], []
    for asset in assets:
        response = requests.get(asset, headers=headers, timeout=10)
        response.raise_for_status()
        singles, graders = _ids_from_bundle(response.text, set_code)
        single_ids.extend(singles)
        grader_ids.extend(graders)

    # The site's primary list comes first, followed by every available grader.
    ids = list(dict.fromkeys(single_ids + grader_ids))
    if not ids:
        raise ValueError(f"No Limited Level-Ups tier lists published for {set_code}")
    return ids
