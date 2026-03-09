from app.pipeline.extractors.base import BaseExtractor, ExtractionResult, ExtractorMethod
from app.config import settings


class LLMExtractor(BaseExtractor):
    """
    Step 5: Last resort. Feed whatever raw text/metadata we have to an LLM
    and ask it to extract a pick. Lower confidence than structured methods.
    """
    method = ExtractorMethod.llm

    SYSTEM_PROMPT = """You are a sports betting pick extractor.
Given raw text from a social media post, extract any sports betting picks mentioned.
Return ONLY a JSON object with this structure:
{
  "found": true/false,
  "picks": [
    {
      "sport": "NFL",
      "event": "Team A vs Team B",
      "pick_type": "spread|moneyline|over_under|prop|parlay",
      "pick_detail": {"team": "...", "line": "..."},
      "odds": "-110",
      "units": null
    }
  ],
  "confidence": 0.0-1.0,
  "notes": "any relevant context"
}
If no picks are found, return {"found": false, "picks": [], "confidence": 0.0}"""

    async def extract(self, source_url: str, raw_metadata: dict) -> ExtractionResult:
        # Gather any text we have — caption, partial transcripts, etc.
        raw_text = " ".join(filter(None, [
            raw_metadata.get("caption", ""),
            raw_metadata.get("description", ""),
            raw_metadata.get("partial_transcript", ""),
            raw_metadata.get("ocr_text", ""),
        ])).strip()

        if not raw_text:
            return self._fail("No raw text available for LLM extraction")

        try:
            result = await self._call_llm(raw_text)
            if not result.get("found"):
                return self._fail("LLM found no picks in content")

            # Pass structured output as text for the parser to consume
            import json
            return self._succeed(json.dumps(result), confidence=result.get("confidence", 0.5))

        except Exception as e:
            return self._fail(str(e))

    async def _call_llm(self, text: str) -> dict:
        import json
        if settings.openai_api_key:
            return await self._openai(text)
        elif settings.anthropic_api_key:
            return await self._anthropic(text)
        else:
            raise RuntimeError("No LLM API key configured")

    async def _openai(self, text: str) -> dict:
        import json
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": text[:4000]},  # Truncate to avoid token waste
            ],
        )
        return json.loads(response.choices[0].message.content)

    async def _anthropic(self, text: str) -> dict:
        import json
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        message = await client.messages.create(
            model="claude-haiku-3-5",
            max_tokens=1024,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text[:4000]}],
        )
        return json.loads(message.content[0].text)
