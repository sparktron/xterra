from xw.parse import get_adapter, generic, xenforo
from xw.parse.base import parse_count

BASE = "https://forum.example.invalid"


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
