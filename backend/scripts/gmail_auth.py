"""
One-time script to authorize Gmail API access for the dedicated
pickreceipts ingestion account.

Usage (run locally, NOT on Railway):
    cd backend
    source venv/bin/activate
    pip install google-auth-oauthlib google-api-python-client
    python scripts/gmail_auth.py

Prereqs:
    scripts/credentials.json  (downloaded from Google Cloud Console:
                               APIs & Services -> Credentials -> OAuth client ID)

Output:
    scripts/token.json        (contains the long-lived refresh token)

Next step:
    Copy the contents of token.json into the GMAIL_TOKEN_JSON env var on Railway,
    and copy credentials.json into GMAIL_CREDENTIALS_JSON.
"""
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

SCRIPT_DIR = Path(__file__).resolve().parent
CREDENTIALS_PATH = SCRIPT_DIR / "credentials.json"
TOKEN_PATH = SCRIPT_DIR / "token.json"


def main() -> None:
    if not CREDENTIALS_PATH.exists():
        raise SystemExit(
            f"Missing {CREDENTIALS_PATH}. Download OAuth client credentials from "
            "Google Cloud Console (Desktop app type) and save them there."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0)

    TOKEN_PATH.write_text(creds.to_json())
    print(f"Wrote {TOKEN_PATH}")
    print("Next: copy its contents into the GMAIL_TOKEN_JSON env var on Railway.")


if __name__ == "__main__":
    main()
