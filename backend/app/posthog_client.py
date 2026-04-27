"""
PostHog analytics client.

Initialized once at import time from env vars. Import `posthog_client`
wherever you need to capture events. It is safe to call capture() even
when POSTHOG_API_KEY is not set — the client will be None and all calls
are no-ops.
"""
import atexit
import logging

from app.config import settings

log = logging.getLogger(__name__)

posthog_client = None

if settings.posthog_api_key:
    try:
        from posthog import Posthog

        posthog_client = Posthog(
            settings.posthog_api_key,
            host=settings.posthog_host,
        )
        atexit.register(posthog_client.shutdown)
        log.info("PostHog client initialized")
    except Exception as exc:  # pragma: no cover
        log.warning("PostHog client failed to initialize: %s", exc)
        posthog_client = None
else:
    log.info("POSTHOG_API_KEY not set — analytics disabled")
