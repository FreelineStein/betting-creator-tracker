import asyncio
import tempfile
import os
from app.pipeline.extractors.base import BaseExtractor, ExtractionResult, ExtractorMethod


class OCRExtractor(BaseExtractor):
    """
    Step 4: Extract key frames from video and run OCR.
    Best for creators who use text overlays / graphics to display their picks.
    """
    method = ExtractorMethod.ocr

    async def extract(self, source_url: str, raw_metadata: dict) -> ExtractionResult:
        try:
            video_url = raw_metadata.get("video_url") or source_url

            with tempfile.TemporaryDirectory() as tmpdir:
                # Extract frames at 1fps using ffmpeg
                frames_pattern = os.path.join(tmpdir, "frame_%04d.jpg")
                ffmpeg_result = await asyncio.create_subprocess_exec(
                    "ffmpeg", "-i", video_url,
                    "-vf", "fps=1",
                    "-q:v", "2",
                    frames_pattern,
                    "-y", "-loglevel", "error",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await ffmpeg_result.communicate()

                frame_files = sorted([
                    os.path.join(tmpdir, f)
                    for f in os.listdir(tmpdir)
                    if f.startswith("frame_")
                ])

                if not frame_files:
                    return self._fail("No frames extracted from video")

                # Run OCR on each frame, collect all text
                all_text = await asyncio.to_thread(self._ocr_frames, frame_files)

            if not all_text.strip():
                return self._fail("OCR returned no text from frames")

            return self._succeed(all_text, confidence=0.7)

        except Exception as e:
            return self._fail(str(e))

    def _ocr_frames(self, frame_files: list) -> str:
        import easyocr
        reader = easyocr.Reader(["en"], gpu=False)
        collected = []
        for frame_path in frame_files:
            results = reader.readtext(frame_path, detail=0)
            if results:
                collected.extend(results)
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for text in collected:
            if text not in seen:
                seen.add(text)
                unique.append(text)
        return " | ".join(unique)
