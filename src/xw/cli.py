"""`xw` command line interface."""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

from . import db, doctor as doctor_mod
from .config import Config
from .crawl import discover, harvest
from .export import export_all
from .extract import extract_pending
from .fetch import Blocked, Fetcher
from .ingest import MANUAL_SOURCE, ingest_file
from .llm import LLM
from .qa import check_wiki
from .review import apply_reviews, export_review
from .topics import TopicIndex
from .verify import verify_pending


def _open(args: argparse.Namespace) -> tuple[Config, sqlite3.Connection]:
    cfg = Config.load(args.root)
    cfg.ensure_dirs()
    conn = db.connect(cfg.db_path)
    db.seed_sources(conn, cfg.sources)
    return cfg, conn


def _sources(conn: sqlite3.Connection, only: str | None, include_blocked: bool = False) -> list[sqlite3.Row]:
    rows = conn.execute("SELECT * FROM sources WHERE enabled=1 ORDER BY rank").fetchall()
    if only:
        rows = [r for r in rows if r["id"] == only]
    if not include_blocked:
        rows = [r for r in rows if r["status"] != "blocked"]
    return rows


def cmd_init(args: argparse.Namespace) -> int:
    cfg, conn = _open(args)
    print(f"initialised {cfg.db_path} with {conn.execute('SELECT COUNT(*) FROM sources').fetchone()[0]} sources")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    return doctor_mod.run(Config.load(args.root), smoke=args.smoke, net=args.net)


def cmd_status(args: argparse.Namespace) -> int:
    cfg, conn = _open(args)
    queries = {
        "threads": "SELECT COUNT(*) FROM threads WHERE source_id=?",
        "queued": "SELECT COUNT(*) FROM threads WHERE source_id=? AND status='queued'",
        "todo": "SELECT COUNT(*) FROM chunks c JOIN threads t ON t.id=c.thread_id WHERE t.source_id=? AND c.status='pending'",
        "facts": "SELECT COUNT(*) FROM facts f JOIN threads t ON t.id=f.thread_id WHERE t.source_id=?",
    }
    print(f"{'source':<22}{'status':<13}{'fetched':>8}{'threads':>9}{'queued':>8}{'chunks todo':>13}{'facts':>7}  note")
    for s in conn.execute("SELECT * FROM sources ORDER BY rank").fetchall():
        n = {k: conn.execute(sql, (s["id"],)).fetchone()[0] for k, sql in queries.items()}
        status = s["status"] if s["enabled"] else "(disabled)"
        print(f"{s['id']:<22}{status:<13}{s['fetch_count']:>8}{n['threads']:>9}{n['queued']:>8}{n['todo']:>13}{n['facts']:>7}  {s['reason']}")
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    cfg, conn = _open(args)
    fetcher = Fetcher(cfg, conn)
    for s in _sources(conn, args.source):
        print(f"discover {s['id']}")
        try:
            discover(cfg, conn, fetcher, s)
        except Blocked as exc:
            db.set_source_status(conn, s["id"], "blocked", exc.reason)
            print(f"  BLOCKED: {exc.reason}")
    return 0


def cmd_harvest(args: argparse.Namespace) -> int:
    cfg, conn = _open(args)
    fetcher = Fetcher(cfg, conn)
    for s in _sources(conn, args.source):
        print(f"harvest {s['id']}")
        try:
            harvest(cfg, conn, fetcher, s, limit=args.limit)
        except Blocked as exc:
            db.set_source_status(conn, s["id"], "blocked", exc.reason)
            print(f"  BLOCKED: {exc.reason}")
    return 0


def _extract(cfg: Config, conn: sqlite3.Connection, source: str | None, limit: int | None) -> int:
    topics = TopicIndex(cfg.topics)
    return extract_pending(cfg, conn, LLM(cfg), topics, source_id=source, limit=limit)


def _verify(cfg: Config, conn: sqlite3.Connection, limit: int | None = None) -> int:
    model = cfg.verify.get("verify_model") or None
    return verify_pending(cfg, conn, LLM(cfg, model=model), limit=limit)


def cmd_verify(args: argparse.Namespace) -> int:
    cfg, conn = _open(args)
    print(f"verified {_verify(cfg, conn, args.limit)} fact(s)")
    return 0


def cmd_review_export(args: argparse.Namespace) -> int:
    cfg, conn = _open(args)
    files = export_review(cfg, conn, TopicIndex(cfg.topics))
    if not files:
        print("nothing to review (run `xw verify` first, or everything is already reviewed)")
        return 0
    for f in files:
        print(f"wrote {f}")
    print("\nNext: in Claude Code, run /review-wiki (or ask the wiki-reviewer agent to review these batches), then `xw review-apply`.")
    return 0


def cmd_review_apply(args: argparse.Namespace) -> int:
    cfg, conn = _open(args)
    stats = apply_reviews(cfg, conn, [Path(p) for p in args.paths] or None, by=args.by)
    rate = stats["verifier_false_accept_rate"]
    print(f"applied {stats['applied']} verdict(s); {stats['invalid']} invalid entr{'y' if stats['invalid'] == 1 else 'ies'} ignored")
    if rate is None:
        print("no audited claims yet, so the local verifier's reliability is not measured")
    else:
        print(f"local verifier false-accept rate: {rate:.0%} ({stats['audited_rejected']}/{stats['audited_supported']} reviewed 'supported' claims rejected)")
        if rate > 0.10:
            print("WARNING: above 10%. Keep verify.require_local_pass on, raise review.audit_rate, or try a second model in verify.verify_model.")
    return 0


def cmd_qa(args: argparse.Namespace) -> int:
    cfg, conn = _open(args)
    bad = check_wiki(cfg, conn)
    for v in bad:
        print(f"VIOLATION: {v}")
    print(f"qa: {'FAILED, ' + str(len(bad)) + ' violation(s)' if bad else 'passed'}")
    return 1 if bad else 0


def cmd_extract(args: argparse.Namespace) -> int:
    cfg, conn = _open(args)
    if not args.watch:
        n = _extract(cfg, conn, args.source, args.limit)
        print(f"processed {n} chunk(s)")
        return 0
    idle = 0
    while idle < args.idle_polls:  # run alongside `xw run --crawl-only` to keep the GPU busy
        n = _extract(cfg, conn, args.source, args.limit)
        idle = idle + 1 if n == 0 else 0
        if n == 0:
            time.sleep(args.poll_s)
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    cfg, conn = _open(args)
    count = 0
    for p in args.paths:
        tid = ingest_file(cfg, conn, Path(p), url=args.url, title=args.title, author=args.author, posted=args.date)
        print(f"{'ingested' if tid else 'nothing usable in'} {p}" + (f" (thread t{tid})" if tid else ""))
        count += 1 if tid else 0
    return 0 if count else 1


def cmd_export(args: argparse.Namespace) -> int:
    cfg, conn = _open(args)
    result = export_all(cfg, conn, TopicIndex(cfg.topics))
    print(f"exported {result['pages']} page(s) from {result['facts']} fact(s); {result['dtc_codes']} DTC row(s); "
          f"{result['dropped']} item(s) withheld; {result['pending']} safety value(s) pending verification; "
          f"{result['disputes']} dispute(s); {result['missing_topics']} topic(s) uncovered")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    cfg, conn = _open(args)
    fetcher = Fetcher(cfg, conn)
    try:
        for s in _sources(conn, args.source):
            sid = s["id"]
            db.set_source_status(conn, sid, "in-progress")
            print(f"== {sid} ({s['name']})")
            try:
                if s["type"] != "manual":
                    discover(cfg, conn, fetcher, s)
                    harvest(cfg, conn, fetcher, s)
                if not args.crawl_only:
                    _extract(cfg, conn, sid, None)
                    _verify(cfg, conn)
            except Blocked as exc:
                db.set_source_status(conn, sid, "blocked", exc.reason)
                print(f"  BLOCKED: {exc.reason}. Moving on; use `xw ingest` for pages you saved yourself.")
                continue
            left = conn.execute("SELECT COUNT(*) FROM threads WHERE source_id=? AND status='queued'", (sid,)).fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM chunks c JOIN threads t ON t.id=c.thread_id WHERE t.source_id=? AND c.status='pending'", (sid,)
            ).fetchone()[0]
            db.set_source_status(conn, sid, "done" if left == 0 and (pending == 0 or args.crawl_only) else "queued")
    except KeyboardInterrupt:
        print("\ninterrupted; state is saved, rerun `xw run` to resume")
    if not args.crawl_only:
        cmd_export(args)
    return 0


def cmd_reset_source(args: argparse.Namespace) -> int:
    _, conn = _open(args)
    db.set_source_status(conn, args.source, "queued")
    conn.execute("UPDATE sources SET fetch_count=0 WHERE id=?", (args.source,))
    conn.commit()
    print(f"{args.source} reset to queued (fetch budget cleared)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="xw", description="Xterra wiki research pipeline (local LLM)")
    p.add_argument("--root", help="repo root (default: current directory, or $XW_ROOT)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create data dir + database and load sources").set_defaults(fn=cmd_init)
    d = sub.add_parser("doctor", help="check Python, config, GPU and the LLM server")
    d.add_argument("--smoke", action="store_true", help="also run a structured-output test against the model")
    d.add_argument("--net", action="store_true", help="also probe each enabled source's home page")
    d.set_defaults(fn=cmd_doctor)
    sub.add_parser("status", help="per-source progress").set_defaults(fn=cmd_status)

    for name, fn, helptext in (("discover", cmd_discover, "queue threads from forum listings"),
                               ("harvest", cmd_harvest, "fetch queued threads and build text chunks")):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("--source")
        if name == "harvest":
            sp.add_argument("--limit", type=int)
        sp.set_defaults(fn=fn)

    e = sub.add_parser("extract", help="run the local LLM over pending chunks")
    e.add_argument("--source")
    e.add_argument("--limit", type=int)
    e.add_argument("--watch", action="store_true", help="keep polling for new chunks (pair with `run --crawl-only`)")
    e.add_argument("--poll-s", type=int, default=30)
    e.add_argument("--idle-polls", type=int, default=10)
    e.set_defaults(fn=cmd_extract)

    i = sub.add_parser("ingest", help="add pages/notes you saved yourself (html, txt, md)")
    i.add_argument("paths", nargs="+")
    i.add_argument("--url", default="", help="original URL, used for attribution (single file)")
    i.add_argument("--title", default="")
    i.add_argument("--author", default="", help="public handle of the original poster")
    i.add_argument("--date", default="")
    i.set_defaults(fn=cmd_ingest)

    v = sub.add_parser("verify", help="local-model fact-check of every extracted claim against its source text")
    v.add_argument("--limit", type=int)
    v.set_defaults(fn=cmd_verify)

    sub.add_parser("export", help="build wiki/ from verified facts").set_defaults(fn=cmd_export)

    sub.add_parser("review-export", help="write claim+excerpt batches for Claude review (data/review/)").set_defaults(fn=cmd_review_export)
    ra = sub.add_parser("review-apply", help="load reviewer verdict files (*.verdicts.json)")
    ra.add_argument("paths", nargs="*")
    ra.add_argument("--by", choices=["claude", "human"], default="claude")
    ra.set_defaults(fn=cmd_review_apply)
    sub.add_parser("qa", help="independent gate: re-check the published wiki against raw source text (exit 1 on violations)").set_defaults(fn=cmd_qa)

    r = sub.add_parser("run", help="discover -> harvest -> extract per source in rank order, then export (resumable)")
    r.add_argument("--source")
    r.add_argument("--crawl-only", action="store_true", help="skip LLM extraction and export")
    r.set_defaults(fn=cmd_run)

    rs = sub.add_parser("reset-source", help="clear blocked status and fetch budget for a source")
    rs.add_argument("source")
    rs.set_defaults(fn=cmd_reset_source)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.fn(args) or 0)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
