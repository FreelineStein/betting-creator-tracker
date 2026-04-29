"""
Bulk-reprocess Source URLs through the live /admin/reprocess-url endpoint.

Use after a parser/enrichment/resolver fix when existing rows still hold
stale picks. Each URL is wiped and re-ingested under the current pipeline,
which now pins `event_id` at submission time and routes unmatchable picks
to needs_review instead of logging them as resolvable.

Filters are AND'd together. Always run with --dry-run first to preview.

    DATABASE_URL='<railway public postgres url>' \
    ADMIN_API_KEY='<admin bearer>' \
    BACKEND_URL='https://believable-mindfulness-production-12eb.up.railway.app' \
        ./venv/bin/python -m scripts.reprocess_urls --only-fallback --dry-run

Filters:
  --before <iso>        Source.scraped_at strictly before this UTC timestamp.
  --creator-id <uuid>   Only sources for this creator.
  --only-fallback       Only sources where any attached pick has
                        event_date == logged_at (the sticky-fallback
                        signature — exactly the rows that were vulnerable
                        to wrong-day matches before the fix).
  --limit N             Cap the number of URLs processed (safety brake).
  --dry-run             List URLs without calling the endpoint.
  --yes                 Skip the interactive confirmation.
  --sleep <float>       Seconds between requests. Default 2.5s — stays
                        under /admin/reprocess-url's 30/min rate limit.
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Pick, Source  # noqa: E402


def parse_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--before", type=parse_iso, default=None)
    parser.add_argument("--creator-id", default=None)
    parser.add_argument("--only-fallback", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--sleep", type=float, default=2.5)
    return parser.parse_args()


def collect_urls(args: argparse.Namespace) -> list[str]:
    """Run the DB-side filter and return matching post URLs (sorted oldest first)."""
    db = SessionLocal()
    try:
        if args.only_fallback:
            # Sticky-fallback signature: any pick where event_date and
            # logged_at match to the microsecond. The parser would never
            # emit an event_date that lines up with a server-set logged_at,
            # so equality reliably indicates the pre-fix poisoning.
            q = (
                db.query(Source)
                .join(Pick, Pick.source_id == Source.source_id)
                .filter(Pick.event_date == Pick.logged_at)
            )
        else:
            q = db.query(Source)

        if args.before:
            q = q.filter(Source.scraped_at < args.before)
        if args.creator_id:
            q = q.filter(Source.creator_id == args.creator_id)

        q = q.order_by(Source.scraped_at.asc())
        # Dedupe in Python — Postgres DISTINCT ON requires the leading
        # ORDER BY to match, and a join on picks can yield the same Source
        # multiple times anyway.
        seen: set[str] = set()
        urls: list[str] = []
        for s in q.all():
            if s.post_url not in seen:
                seen.add(s.post_url)
                urls.append(s.post_url)
        if args.limit is not None:
            urls = urls[: args.limit]
        return urls
    finally:
        db.close()


def main() -> int:
    args = parse_args()

    if not (args.only_fallback or args.before or args.creator_id):
        print(
            "refusing to run with no filter — pass --only-fallback, --before, "
            "or --creator-id (or some combination).",
            file=sys.stderr,
        )
        return 2

    backend_url = os.environ.get(
        "BACKEND_URL",
        "https://believable-mindfulness-production-12eb.up.railway.app",
    ).rstrip("/")
    admin_key = os.environ.get("ADMIN_API_KEY", "")

    if not args.dry_run and not admin_key:
        print("ADMIN_API_KEY env var is required (unless --dry-run).", file=sys.stderr)
        return 2

    urls = collect_urls(args)
    print(f"Matched {len(urls)} source URLs.")
    if not urls:
        return 0

    preview = urls[:8]
    for u in preview:
        print(f"  {u}")
    if len(urls) > len(preview):
        print(f"  …and {len(urls) - len(preview)} more")

    if args.dry_run:
        return 0

    if not args.yes:
        confirm = input(
            f"Reprocess all {len(urls)} URLs against {backend_url}? [yes/N]: "
        ).strip().lower()
        if confirm not in ("y", "yes"):
            print("aborted.")
            return 1

    endpoint = f"{backend_url}/api/v1/admin/reprocess-url"
    headers = {
        "Authorization": f"Bearer {admin_key}",
        "Content-Type": "application/json",
    }

    ok = 0
    failed = 0
    needs_review = 0
    deleted_total = 0
    new_total = 0

    with httpx.Client(timeout=60.0) as client:
        for i, url in enumerate(urls, start=1):
            try:
                r = client.post(endpoint, headers=headers, json={"url": url})
            except httpx.HTTPError as e:
                failed += 1
                print(f"[{i}/{len(urls)}] ERROR (network) {url} — {e}")
                time.sleep(args.sleep)
                continue

            if r.status_code == 200:
                body = r.json()
                deleted = body.get("deleted_pick_count", 0)
                new = body.get("new_pick_count", 0)
                deleted_total += deleted
                new_total += new
                # The endpoint mirrors /submissions and doesn't surface a
                # "needs_review" flag yet; new_pick_count == 0 with
                # deleted > 0 is the closest proxy.
                tag = " (review)" if new == 0 else ""
                if new == 0:
                    needs_review += 1
                print(
                    f"[{i}/{len(urls)}] ok{tag} {url} — "
                    f"deleted={deleted} new={new}"
                )
                ok += 1
            else:
                failed += 1
                detail = ""
                try:
                    detail = r.json().get("detail", "")
                except Exception:
                    detail = r.text[:200]
                print(
                    f"[{i}/{len(urls)}] HTTP {r.status_code} {url} — {detail}"
                )

            time.sleep(args.sleep)

    print(
        f"\nSUMMARY: ok={ok} failed={failed} likely_needs_review={needs_review} "
        f"deleted_picks={deleted_total} new_picks={new_total}"
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
