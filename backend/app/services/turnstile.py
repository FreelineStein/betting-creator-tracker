"""
Cloudflare Turnstile token verification.

Frontend renders the Turnstile widget with the site key and submits the
resulting token alongside the form. We verify the token server-side here
before treating the submission as legitimate.

Docs: https://developers.cloudflare.com/turnstile/get-started/server-side-validation/
For local dev, use the always-pass test secret: 1x0000000000000000000000000000000AA
"""
from typing import Optional

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile_token(token: str, remote_ip: Optional[str] = None) -> bool:
    """
    Return True iff Cloudflare confirms the token is valid for our site.

    Raises RuntimeError if the secret key is not configured — callers should
    surface this as a 503 so misconfigured deploys fail loud rather than
    silently bypassing the bot check.
    """
    if not settings.turnstile_secret_key:
        raise RuntimeError("turnstile_secret_key is not configured")
    if not token:
        return False

    payload = {"secret": settings.turnstile_secret_key, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(SITEVERIFY_URL, data=payload)
        resp.raise_for_status()
        body = resp.json()
    except Exception as e:
        log.error("turnstile_verify_request_failed", error=str(e))
        return False

    success = bool(body.get("success"))
    if not success:
        log.warning("turnstile_verify_rejected", error_codes=body.get("error-codes"))
    return success
