"""Shared parsing types and helpers."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup, Tag


@dataclass
class ThreadStub:
    url: str
    title: str
    pinned: bool = False
    author: str = ""
    replies: int = 0
    views: int = 0


@dataclass
class ForumPage:
    threads: list[ThreadStub] = field(default_factory=list)
    subforums: list[tuple[str, str]] = field(default_factory=list)
    next_url: str | None = None


@dataclass
class Post:
    author: str
    posted: str
    text: str
    post_id: str = ""


@dataclass
class ThreadPage:
    title: str
    posts: list[Post]
    next_url: str | None = None


def absolute(base: str, href: str) -> str:
    return urldefrag(urljoin(base, href))[0]


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def same_site(a: str, b: str) -> bool:
    return _host(a) == _host(b)


def parse_count(text: str) -> int:
    """'1.2K' -> 1200, '3,456' -> 3456, '2M' -> 2000000."""
    t = text.strip().lower().replace(",", "")
    m = re.match(r"^(\d+(?:\.\d+)?)([km]?)$", t)
    if not m:
        return 0
    n = float(m.group(1))
    return int(n * {"": 1, "k": 1_000, "m": 1_000_000}[m.group(2)])


_BLOCK_TAGS = ["p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "ul", "ol", "table", "blockquote"]


def html_to_text(node: Tag, base_url: str = "", max_images: int = 10) -> str:
    """Readable text from an HTML node. Quotes are dropped (they duplicate other posts); images become
    `[image: URL]` markers so diagram links can be cataloged; line structure is preserved."""
    soup = BeautifulSoup(str(node), "lxml")
    for t in soup.select("script, style, noscript, .bbCodeBlock--quote, .bbCodeBlock-expandLink, blockquote"):
        t.decompose()
    kept = 0
    for img in soup.find_all("img"):
        src = img.get("data-url") or img.get("src") or ""
        classes = " ".join(img.get("class", []))
        if src.startswith(("http://", "https://", "/")) and "smilie" not in classes and kept < max_images:
            img.replace_with(f" [image: {absolute(base_url, src) if base_url else src}] ")
            kept += 1
        else:
            img.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for li in soup.find_all("li"):
        li.insert(0, "- ")
    for tag in soup.find_all(_BLOCK_TAGS):
        tag.append("\n")
    text = soup.get_text()
    text = re.sub(r"[ \t ]+", " ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
