import asyncio
import tempfile
import os
from app.pipeline.extractors.base import BaseExtractor, ExtractionResult, ExtractorMethod


class WhisperExtractor(BaseExtractor):
    """
    Step 3: Download video, extract audio, transcribe with faster-whisper.
    Most reliable for video-only picks. Slower and heavier than caption/subtitle methods.
    """
    method = ExtractorMethod.whisper

    async def extract(self, source_url: str, raw_metadata: dict) -> ExtractionResult:
        try:
            video_url = raw_metadata.get("video_url") or source_url

            with tempfile.TemporaryDirectory() as tmpdir:
                audio_path = os.path.join(tmpdir, "audio.mp3")

                # Download audio via yt-dlp
                download_result = await asyncio.create_subprocess_exec(
                    "yt-dlp",
                    "--extract-audio",
                    "--audio-format", "mp3",
                    "--output", audio_path,
                    "--quiet",
                    video_url,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await download_result.communicate()

                if download_result.returncode != 0:
                    return self._fail(f"yt-dlp failed: {stderr.decode()[:200]}")

                if not os.path.exists(audio_path):
                    return self._fail("Audio file not found after download")

                # Transcribe with faster-whisper
                transcript = await asyncio.to_thread(self._transcribe, audio_path)

            if not transcript:
                return self._fail("Whisper returned empty transcript")

            return self._succeed(transcript, confidence=0.85)

        except Exception as e:
            return self._fail(str(e))

    def _transcribe(self, audio_path: str) -> str:
        from faster_whisper import WhisperModel
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(audio_path, beam_size=5)
        return " ".join(segment.text.strip() for segment in segments)
