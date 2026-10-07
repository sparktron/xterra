"""Generic adapter: one page in, one "post" of main-content text out. No forum discovery.

Use it for single articles, vendor install guides and pages you saved by hand (`xw ingest`)."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .base import ForumPage, Post, ThreadPage, html_to_text

_CANDIDATES = ["article", "main", "#content", "#main", ".post", ".entry-content", ".content", "body"]
_NOISE = "nav, header, footer, aside, form, .sidebar, .menu, .breadcrumb, .comments, script, style"


def parse_forum(html: str, url: str) -> ForumPage:
    return ForumPage()  # discovery is not supported for unknown layouts; list thread_urls in sources.yaml


def parse_thread(html: str, url: str) -> ThreadPage:
    soup = BeautifulSoup(html, "lxml")
    for t in soup.select(_NOISE):
        t.decompose()
    title_tag = soup.find("h1") or soup.title
    title = title_tag.get_text(" ", strip=True) if title_tag else url
    title = re.sub(r"\s+", " ", title)
    text = ""
    for sel in _CANDIDATES:
        node = soup.select_one(sel)
        if node is not None:
            text = html_to_text(node, url)
            if len(text) > 200:
                break
    return ThreadPage(title=title, posts=[Post(author="", posted="", text=text)] if text else [])
