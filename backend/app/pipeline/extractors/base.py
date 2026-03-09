from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class ExtractorMethod(str, Enum):
    caption = "caption"
    subtitles = "subtitles"
    whisper = "whisper"
    ocr = "ocr"
    llm = "llm"


@dataclass
class ExtractionResult:
    method: ExtractorMethod
    success: bool
    text: Optional[str] = None           # Raw extracted text
    confidence: float = 0.0              # 0.0 - 1.0
    error: Optional[str] = None          # Error message if failed

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "success": self.success,
            "confidence": self.confidence,
            "error": self.error,
            # Don't store full text in attempt log — it lives on Source.raw_content
        }


class BaseExtractor(ABC):
    """
    All extractors follow the same interface.
    Return an ExtractionResult — never raise exceptions.
    """

    method: ExtractorMethod

    @abstractmethod
    async def extract(self, source_url: str, raw_metadata: dict) -> ExtractionResult:
        """
        Attempt to extract raw text from the source.
        raw_metadata: whatever the scraper returned (caption, post data, etc.)
        """
        ...

    def _fail(self, error: str) -> ExtractionResult:
        return ExtractionResult(
            method=self.method,
            success=False,
            confidence=0.0,
            error=error,
        )

    def _succeed(self, text: str, confidence: float = 1.0) -> ExtractionResult:
        return ExtractionResult(
            method=self.method,
            success=True,
            text=text,
            confidence=confidence,
        )
