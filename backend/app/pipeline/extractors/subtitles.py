from app.pipeline.extractors.base import BaseExtractor, ExtractionResult, ExtractorMethod


class SubtitleExtractor(BaseExtractor):
    """
    Step 2: Pull auto-generated captions/subtitles from the platform.
    YouTube has reliable auto-captions. Instagram/TikTok less so, but worth trying.
    """
    method = ExtractorMethod.subtitles

    async def extract(self, source_url: str, raw_metadata: dict) -> ExtractionResult:
        subtitles = (
            raw_metadata.get("subtitles")
            or raw_metadata.get("auto_captions")
            or raw_metadata.get("transcript")
            or ""
        )
        subtitles = subtitles.strip()

        if not subtitles:
            return self._fail("No subtitles or auto-captions available")

        # Subtitles are generally reliable when present
        return self._succeed(subtitles, confidence=0.8)
