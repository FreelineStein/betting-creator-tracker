"""
Run the Twitter notification parser against a saved .eml file.

Usage:
    cd backend
    source venv/bin/activate
    python scripts/test_gmail_parse.py path/to/notification.eml

Prints what the adapter would have extracted — handle, tweet text, URL,
media URLs — without touching the Gmail API. Iterate on the parser by
re-running this until the output looks right, then drop the .eml into
backend/tests/fixtures/ as a regression fixture.
"""
import json
import sys
from pathlib import Path

# Make `app` importable when running this script directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.adapters.twitter_gmail import parse_eml_bytes  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python scripts/test_gmail_parse.py <path-to.eml>")
        raise SystemExit(2)

    path = Path(sys.argv[1])
    if not path.exists():
        raise SystemExit(f"file not found: {path}")

    result = parse_eml_bytes(path.read_bytes())
    if result is None:
        print("PARSER RETURNED NONE — could not extract a tweet from this email.")
        raise SystemExit(1)

    raw_post, metadata = result
    print("=== RawPost ===")
    print(json.dumps({
        "platform": raw_post.platform,
        "post_type": raw_post.post_type,
        "post_url": raw_post.post_url,
        "posted_at": raw_post.posted_at.isoformat() if raw_post.posted_at else None,
        "caption": raw_post.caption,
        "description": raw_post.description,
        "raw": raw_post.raw,
    }, indent=2, default=str))
    print()
    print("=== NotificationMetadata ===")
    print(json.dumps({
        "notification_id": metadata.notification_id,
        "received_at": metadata.received_at.isoformat(),
        "source_platform": metadata.source_platform,
        "raw_notification_preview": (metadata.raw_notification or "")[:300] + "...",
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
