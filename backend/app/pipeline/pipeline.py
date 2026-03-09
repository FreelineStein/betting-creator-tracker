import structlog
from typing import Optional
from app.pipeline.extractors.base import ExtractionResult
from app.pipeline.extractors.caption import CaptionExtractor
from app.pipeline.extractors.subtitles import SubtitleExtractor
from app.pipeline.extractors.whisper import WhisperExtractor
from app.pipeline.extractors.ocr import OCRExtractor
from app.pipeline.extractors.llm import LLMExtractor
from app.config import settings

log = structlog.get_logger()

# Confidence threshold to accept a result and stop the cascade
CONFIDENCE_THRESHOLD = 0.6

# Ordered pipeline — cheapest/fastest first
EXTRACTOR_PIPELINE = [
    CaptionExtractor(),
    SubtitleExtractor(),
    WhisperExtractor(),
    OCRExtractor(),
    LLMExtractor(),
]


async def run_extraction_pipeline(
    source_url: str,
    raw_metadata: dict,
) -> tuple[Optional[str], list[dict]]:
    """
    Run extractors in order, stopping at the first confident result.

    Returns:
        (extracted_text, attempts_log)
        extracted_text is None if all extractors failed.
    """
    attempts = []

    for extractor in EXTRACTOR_PIPELINE:
        log.info("Trying extractor", method=extractor.method, url=source_url)

        result: ExtractionResult = await extractor.extract(source_url, raw_metadata)
        attempts.append(result.to_dict())

        if result.success and result.confidence >= CONFIDENCE_THRESHOLD:
            log.info(
                "Extraction succeeded",
                method=result.method,
                confidence=result.confidence,
            )
            return result.text, attempts

        log.info(
            "Extractor did not meet threshold",
            method=result.method,
            success=result.success,
            confidence=result.confidence,
            error=result.error,
        )

    # All extractors failed or low confidence
    log.warning("All extractors failed", url=source_url)

    if settings.failed_extraction_notify:
        await _notify_failed_extraction(source_url, attempts)

    return None, attempts


async def _notify_failed_extraction(source_url: str, attempts: list[dict]):
    """
    Notify when extraction fails so we can debug edge cases.
    TODO: hook this up to Discord/email/webhook notification.
    """
    log.error(
        "FAILED EXTRACTION — needs review",
        url=source_url,
        attempts=attempts,
    )
