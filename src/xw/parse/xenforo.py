"""XenForo 2.x adapter (forum listings and thread pages).

Selectors are validated against both stock XenForo 2 markup and heavily customised themes
(e.g. thenewx.org's "california" theme, where posts are <article class="js-post ..."> without the
stock message--post class). tests/fixtures hold representative samples of each to adjust against.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from .base import ForumPage, Post, ThreadPage, ThreadStub, absolute, html_to_text, parse_count


def _next_url(soup: BeautifulSoup, url: str) -> str | None:
    a = soup.select_one("a.pageNav-jump--next[href]")
    return absolute(url, a["href"]) if a else None


def parse_forum(html: str, url: str) -> ForumPage:
    soup = BeautifulSoup(html, "lxml")
    page = ForumPage(next_url=_next_url(soup, url))

    for item in soup.select("div.structItem--thread"):
        links = [a for a in item.select("div.structItem-title a[href]") if "/threads/" in a["href"]]
        if not links:
            continue
        primary = next((a for a in links if a.has_attr("data-tp-primary")), links[-1])
        stub = ThreadStub(
            url=absolute(url, primary["href"]),
            title=primary.get_text(" ", strip=True),
            pinned=item.select_one(".structItem-status--sticky") is not None,
            author=item.get("data-author", ""),
        )
        for dl in item.select(".structItem-cell--meta dl"):
            dt, dd = dl.find("dt"), dl.find("dd")
            if not dt or not dd:
                continue
            label = dt.get_text(strip=True).lower()
            if label.startswith("repl"):
                stub.replies = parse_count(dd.get_text(strip=True))
            elif label.startswith("view"):
                stub.views = parse_count(dd.get_text(strip=True))
        page.threads.append(stub)

    seen: set[str] = set()
    for a in soup.select(".node-title a[href]"):
        href = a["href"]
        if "/forums/" in href:
            u = absolute(url, href)
            if u not in seen:
                seen.add(u)
                page.subforums.append((a.get_text(" ", strip=True), u))
    return page


def parse_thread(html: str, url: str) -> ThreadPage:
    soup = BeautifulSoup(html, "lxml")
    # Some captures carry an empty <h1 class="p-title-value"> placeholder, so require text.
    h1 = soup.select_one("h1.p-title-value")
    title = ""
    if h1 is not None and h1.get_text(strip=True):
        for label in h1.select(".label, .labelLink"):
            label.decompose()
        title = h1.get_text(" ", strip=True)
    if not title:
        # custom themes may use a plain <h1> (e.g. thenewx.org "california" theme);
        # some pages also carry an empty structural h1, so take the first non-empty one
        plain_h1 = next((h for h in soup.find_all("h1") if h.get_text(strip=True)), None)
        title = plain_h1.get_text(" ", strip=True) if plain_h1 else (soup.title.get_text(strip=True) if soup.title else url)

    posts: list[Post] = []
    # Stock XF2 markup uses article.message--post; heavily customised themes (e.g. thenewx.org
    # "california") use article.js-post instead. The bbWrapper requirement below still filters out
    # non-post elements that carry either class.
    for art in soup.select("article.message--post, article.js-post"):
        body = art.select_one(".bbWrapper")
        if body is None:
            continue
        time_tag = art.select_one("time.u-dt")
        posts.append(
            Post(
                author=art.get("data-author", "") or (art.select_one(".message-name") or art).get_text(" ", strip=True)[:60],
                posted=(time_tag.get("datetime", "") if time_tag else ""),
                text=html_to_text(body, url),
                post_id=art.get("id", ""),
            )
        )
    return ThreadPage(title=title, posts=posts, next_url=_next_url(soup, url))
