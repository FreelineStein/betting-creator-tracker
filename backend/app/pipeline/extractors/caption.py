from app.pipeline.extractors.base import BaseExtractor, ExtractionResult, ExtractorMethod


class CaptionExtractor(BaseExtractor):
    """
    Step 1: Cheapest option — pull text directly from post caption/description.
    Works for any platform where the creator writes their pick in the caption.
    """
    method = ExtractorMethod.caption

    async def extract(self, source_url: str, raw_metadata: dict) -> ExtractionResult:
        caption = raw_metadata.get("caption") or raw_metadata.get("description") or ""
        caption = caption.strip()

        if not caption:
            return self._fail("No caption or description found")

        if len(caption) < 10:
            return self._fail("Caption too short to contain a pick")

        # Basic confidence heuristic: does it contain betting keywords?
        betting_keywords = [
            "spread", "line", "over", "under", "ml", "moneyline",
            "lock", "play", "unit", "bet", "-", "+"
        ]
        keyword_hits = sum(1 for kw in betting_keywords if kw.lower() in caption.lower())
        confidence = min(0.5 + (keyword_hits * 0.1), 1.0)

        return self._succeed(caption, confidence=confidence)
