import httpx
import pytest

from xw.fetch import Blocked, BudgetExceeded, Disallowed, FetchError, Fetcher

PAGE = "<html><body>" + "<p>Real forum content about control arms.</p>" * 40 + "</body></html>"


def make(cfg, conn, handler):
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False,
                          headers={"User-Agent": "test"})
    return Fetcher(cfg, conn, client=client, sleep=lambda s: None)


def robots_ok(request):
    if request.url.path == "/robots.txt":
        return httpx.Response(200, text="User-agent: *\nAllow: /\n")
    return None


def test_fetch_caches_and_counts(cfg, conn):
    calls = []

    def handler(req):
        calls.append(req.url.path)
        return robots_ok(req) or httpx.Response(200, text=PAGE)

    f = make(cfg, conn, handler)
    a = f.get("https://site.invalid/threads/1/", "thenewx")
    b = f.get("https://site.invalid/threads/1/", "thenewx")
    assert not a.from_cache and b.from_cache and a.text == b.text
    assert calls.count("/threads/1/") == 1
    assert conn.execute("SELECT fetch_count FROM sources WHERE id='thenewx'").fetchone()[0] == 1


@pytest.mark.parametrize("status", [401, 402, 403])
def test_stop_statuses_block_the_source(cfg, conn, status):
    f = make(cfg, conn, lambda req: robots_ok(req) or httpx.Response(status, text="no"))
    with pytest.raises(Blocked) as exc:
        f.get("https://site.invalid/threads/1/", "thenewx")
    assert exc.value.status == status


def test_offsite_redirect_is_refused(cfg, conn):
    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(302, headers={"location": "https://paywall.other.invalid/pay"})

    f = make(cfg, conn, handler)
    with pytest.raises(Blocked, match="off-site"):
        f.get("https://site.invalid/threads/1/", "thenewx")


def test_same_site_redirect_is_followed(cfg, conn):
    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        if req.url.path == "/old":
            return httpx.Response(301, headers={"location": "https://www.site.invalid/new"})
        return httpx.Response(200, text=PAGE)

    assert make(cfg, conn, handler).get("https://site.invalid/old", "thenewx").status == 200


def test_robots_disallow(cfg, conn):
    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private/\n")
        return httpx.Response(200, text=PAGE)

    f = make(cfg, conn, handler)
    with pytest.raises(Disallowed):
        f.get("https://site.invalid/private/x", "thenewx")
    assert f.get("https://site.invalid/public/x", "thenewx").status == 200


def test_robots_cross_host_redirect_is_read_not_trusted_blindly(cfg, conn):
    """robots.txt may redirect off-site (it did for the real forum); its rules are still honoured."""
    def handler(req):
        if req.url.host == "site.invalid" and req.url.path == "/robots.txt":
            return httpx.Response(302, headers={"location": "https://robots.other.invalid/robots.txt"})
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /\n")
        return httpx.Response(200, text=PAGE)

    with pytest.raises(Disallowed):
        make(cfg, conn, handler).get("https://site.invalid/threads/1/", "thenewx")


def test_budget(cfg, conn):
    f = make(cfg, conn, lambda req: robots_ok(req) or httpx.Response(200, text=PAGE))
    f.get("https://site.invalid/a", "thenewx", budget=1)
    with pytest.raises(BudgetExceeded):
        f.get("https://site.invalid/b", "thenewx", budget=1)


def test_429_backoff_then_success(cfg, conn):
    state = {"n": 0}
    sleeps = []

    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        state["n"] += 1
        return httpx.Response(429, headers={"retry-after": "7"}) if state["n"] == 1 else httpx.Response(200, text=PAGE)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    f = Fetcher(cfg, conn, client=client, sleep=sleeps.append)
    assert f.get("https://site.invalid/a", "thenewx").status == 200
    assert 7.0 in sleeps


def test_repeated_429_blocks(cfg, conn):
    f = make(cfg, conn, lambda req: robots_ok(req) or httpx.Response(429))
    with pytest.raises(Blocked):
        f.get("https://site.invalid/a", "thenewx")


def test_challenge_page_is_a_block_not_content(cfg, conn):
    f = make(cfg, conn, lambda req: robots_ok(req) or httpx.Response(200, text="<html>Just a moment... verify you are human (captcha)</html>"))
    with pytest.raises(Blocked, match="challenge"):
        f.get("https://site.invalid/a", "thenewx")


def test_404_is_recorded_not_raised(cfg, conn):
    f = make(cfg, conn, lambda req: robots_ok(req) or httpx.Response(404))
    assert f.get("https://site.invalid/gone", "thenewx").status == 404
    assert f.get("https://site.invalid/gone", "thenewx").from_cache


def test_500_is_a_fetch_error(cfg, conn):
    f = make(cfg, conn, lambda req: robots_ok(req) or httpx.Response(500))
    with pytest.raises(FetchError):
        f.get("https://site.invalid/a", "thenewx")
