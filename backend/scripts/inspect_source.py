"""
Read-only — print a Source row by post_url (or URL substring).

Use to see what raw_content + extraction_attempts the pipeline captured
for a tweet so we can tell whether the parser failed because there was
no text, the OCR returned junk, or the LLM produced empty legs.

    DATABASE_URL='<railway public postgres url>' \
        ./venv/bin/python -m scripts.inspect_source <url_or_substring>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import Source  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: scripts/inspect_source.py <url_or_substring>", file=sys.stderr)
        return 2
    needle = sys.argv[1]

    db = SessionLocal()
    try:
        rows = db.query(Source).filter(Source.post_url.like(f"%{needle}%")).all()
        if not rows:
            print(f"No source matches {needle!r}.")
            return 1
        if len(rows) > 1:
            print(f"{len(rows)} sources match. Showing all.\n")

        for s in rows:
            print(f"source_id        : {s.source_id}")
            print(f"creator_id       : {s.creator_id}")
            print(f"platform         : {s.platform.value if hasattr(s.platform, 'value') else s.platform}")
            print(f"post_url         : {s.post_url}")
            print(f"posted_at        : {s.posted_at}")
            print(f"scraped_at       : {s.scraped_at}")
            print(f"extraction_status: "
                  f"{s.extraction_status.value if hasattr(s.extraction_status, 'value') else s.extraction_status}")
            print(f"raw_content      :")
            print(repr(s.raw_content))
            print(f"\nextraction_attempts:")
            try:
                print(json.dumps(s.extraction_attempts, indent=2, default=str))
            except (TypeError, ValueError):
                print(repr(s.extraction_attempts))
            print(f"\nlinked picks ({len(s.picks)}):")
            for p in s.picks:
                pt = p.pick_type.value if hasattr(p.pick_type, "value") else p.pick_type
                print(
                    f"  [{p.pick_id[:8]}] {pt} sport={p.sport} status={p.status.value} "
                    f"event={p.event!r}"
                )
            print()
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
