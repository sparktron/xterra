from xw.parse import get_adapter, generic, xenforo
from xw.parse.base import absolute, parse_count

BASE = "https://forum.example.invalid"


def test_a_malformed_link_in_a_post_does_not_stop_the_harvest():
    # a real xterranation post: an <img src> urllib rejects as "Invalid IPv6 URL" crashed `xw harvest`
    assert absolute(f"{BASE}/threads/x.1/", "http://[broken/pic.jpg") == "http://[broken/pic.jpg"
    html = (f'<article class="message--post" data-author="a"><div class="bbWrapper">Text before'
            f'<img src="http://[broken/pic.jpg"> and after.</div></article>')
    page = xenforo.parse_thread(html, f"{BASE}/threads/x.1/")
    assert "Text before" in page.posts[0].text and "and after." in page.posts[0].text


def test_parse_count():
    assert parse_count("45.2K") == 45200
    assert parse_count("9,800") == 9800
    assert parse_count("2M") == 2_000_000
    assert parse_count("n/a") == 0


def test_xenforo_forum_listing(fixtures):
    page = xenforo.parse_forum((fixtures / "xenforo_forum.html").read_text(), f"{BASE}/forums/diy-how-to.12/")
    titles = {t.title: t for t in page.threads}
    assert "READ FIRST: Engine code list" in titles  # prefix label link must not become the title
    sticky = titles["READ FIRST: Engine code list"]
    assert sticky.pinned and sticky.views == 45200 and sticky.replies == 120 and sticky.author == "old_x_guy"
    assert sticky.url == f"{BASE}/threads/read-first-code-list.101/"
    assert not titles["How to replace lower control arms"].pinned
    assert titles["How to replace lower control arms"].views == 9800
    assert page.next_url == f"{BASE}/forums/diy-how-to.12/page-2"
    assert ("For Sale", f"{BASE}/forums/for-sale.30/") in page.subforums


def test_xenforo_forum_listing_without_friendly_urls(fixtures):
    # XenForo with friendly URLs off (xterranation.org) links "index.php?threads/..." and "index.php?forums/..."
    html = (fixtures / "xenforo_forum.html").read_text().replace('href="/threads/', 'href="/index.php?threads/') \
        .replace('href="/forums/', 'href="/index.php?forums/')
    page = xenforo.parse_forum(html, f"{BASE}/index.php?forums/diy-how-to.12/")
    titles = {t.title: t for t in page.threads}
    assert titles["READ FIRST: Engine code list"].url == f"{BASE}/index.php?threads/read-first-code-list.101/"
    assert ("For Sale", f"{BASE}/index.php?forums/for-sale.30/") in page.subforums


def test_xenforo_thread(fixtures):
    url = f"{BASE}/threads/how-to-replace-lower-control-arms.202/"
    page = xenforo.parse_thread((fixtures / "xenforo_thread.html").read_text(), url)
    assert page.title == "How to replace lower control arms"  # label span removed
    assert [p.author for p in page.posts] == ["trail_dave", "rock_crawler", "bumper"]
    first = page.posts[0]
    assert first.posted.startswith("2014-05-10")
    assert "83 ft-lb" in first.text and "54500-EA000" in first.text
    assert "- Loosen the lug nuts" in first.text  # list structure kept
    assert "[image: https://example.invalid/diagrams/front-susp.png]" in first.text
    assert "smile.gif" not in first.text  # smilies dropped
    assert "Torque the inner pivot bolts to 83 ft-lb" not in page.posts[1].text.split("Confirming")[0]  # quote removed
    assert page.next_url == f"{url}page-2"


def test_xenforo_thread_custom_theme(fixtures):
    # thenewx.org "california" theme: posts are <article class="js-post ..."> without the stock
    # message--post class, and the title is a plain <h1> rather than h1.p-title-value.
    url = f"{BASE}/threads/torn-oil-hose.291789/"
    page = xenforo.parse_thread((fixtures / "xenforo_thread_california.html").read_text(), url)
    assert page.title == "Torn Oil Hose during Timing Chain Guide Job"  # no site suffix from <title>
    assert [p.author for p in page.posts] == ["RamTest", "bw_hairston"]
    assert page.posts[0].posted.startswith("2025-05-30")
    assert all(p.text.strip() for p in page.posts)


def test_generic_thread_extracts_main_text():
    html = "<html><head><title>Guide</title></head><body><nav>menu menu</nav><article><h1>Oil change</h1><p>" + "Drain the oil. " * 30 + "</p></article><footer>copyright</footer></body></html>"
    page = generic.parse_thread(html, "https://x.invalid/guide")
    assert page.title == "Oil change"
    assert "Drain the oil." in page.posts[0].text
    assert "menu" not in page.posts[0].text and "copyright" not in page.posts[0].text


def test_adapter_registry():
    assert get_adapter("xenforo") is xenforo
    try:
        get_adapter("nope")
    except ValueError as exc:
        assert "unknown adapter" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_xenforo_post_date_comes_from_the_permalink_not_the_first_time_tag():
    """In the ingested thenewx threads some authors carry one date on every post and replies predate post 1, i.e. the
    first <time> in the article was not the post's own. The post date sits on its permalink in both themes."""
    html = """<html><body><h1 class="p-title-value">How-to: x</h1>
      <article class="message message--post" data-author="op"><div class="message-userExtras"><dl><dt>Joined</dt>
        <dd><time class="u-dt" datetime="2006-01-28T10:00:00-0500">Jan 28, 2006</time></dd></dl></div>
        <header class="message-attribution"><a class="message-attribution-main" href="/p/1">
          <time class="u-dt" datetime="2011-04-10T09:00:00-0400">Apr 10, 2011</time></a></header>
        <div class="bbWrapper">Guide text</div></article>
      <article class="js-post" data-author="b"><div class="MessageCard"><span class="member-since">
        <time class="u-dt" datetime="2009-09-22T08:00:00-0400">Sep 22, 2009</time></span>
        <a class="MessageCard__date-created" href="/p/2"><time class="u-dt" datetime="2011-04-12T09:00:00-0400">Apr 12</time></a>
        <div class="bbWrapper">Reply text</div></div></article></body></html>"""
    page = xenforo.parse_thread(html, f"{BASE}/threads/x.1/")
    assert [p.posted[:10] for p in page.posts] == ["2011-04-10", "2011-04-12"]


def test_xenforo_opening_post_in_a_messagecard_div_is_not_dropped():
    """thenewx.org's later "california" markup (2025 captures) puts the opening post in <div class="MessageCard js-post">
    with no data-author, its author in <meta itemprop="name"> and its date only as text on the permalink; the
    replies stay <article class="js-post">. The opening post was dropped, i.e. every how-to lost its guide."""
    html = """<html><body><h1>How-to: bypass</h1>
      <div class="MessageCard js-messageCard js-post" id="js-post-1"><meta itemprop="name" content="JOSX2">
        <span class="edited"><time class="u-dt" datetime="2023-08-09T17:00:52-0400">Aug 9, 2023</time></span>
        <a class="MessageCard__date-created" href="/p/1">Jul 3, 2010(Edited)</a>
        <article class="message-body"><div class="bbWrapper">Swap these two hoses.</div></article>
        <div class="signature-content-wrapper"><div class="bbWrapper">my signature</div></div></div>
      <article class="js-post" data-author="KAK"><a class="MessageCard__date-created" href="/p/2">
        <time class="u-dt" datetime="2010-07-03T09:00:00-0400">Jul 3, 2010</time></a>
        <div class="bbWrapper">I like this one</div></article></body></html>"""
    page = xenforo.parse_thread(html, f"{BASE}/threads/x.1/")
    assert [(p.author, p.posted[:10], p.text) for p in page.posts] == [
        ("JOSX2", "2010-07-03", "Swap these two hoses."), ("KAK", "2010-07-03", "I like this one")]
