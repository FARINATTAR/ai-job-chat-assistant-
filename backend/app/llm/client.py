"""
Provider-agnostic LLM client supporting Gemini and OpenAI.
Features structured JSON parsing, retry logic, and deterministic fallback for offline/test environments.
"""
import json
import re
from typing import Dict, Any, Optional
from ..config import settings


class LLMClient:
    """Wrapper supporting Gemini and OpenAI with structured JSON parsing."""

    def __init__(self):
        self.gemini_key = settings.GEMINI_API_KEY
        self.openai_key = settings.OPENAI_API_KEY
        self._provider = "fallback"

        if self.gemini_key:
            self._provider = "gemini"
            import google.generativeai as genai
            genai.configure(api_key=self.gemini_key)
            self._gemini_model = genai.GenerativeModel("gemini-1.5-flash")
        elif self.openai_key:
            self._provider = "openai"
            from openai import OpenAI
            self._openai_client = OpenAI(api_key=self.openai_key)

    @property
    def provider(self) -> str:
        return self._provider

    def generate_text(self, prompt: str, system_instruction: str = "") -> str:
        """Generate unstructured response."""
        if self._provider == "gemini":
            try:
                full_prompt = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt
                response = self._gemini_model.generate_content(full_prompt)
                return response.text.strip()
            except Exception as e:
                print(f"[LLMClient] Gemini error: {e}")

        elif self._provider == "openai":
            try:
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})

                response = self._openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                    temperature=0.2
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                print(f"[LLMClient] OpenAI error: {e}")

        # Deterministic fallback text
        return ""

    def generate_json(self, prompt: str, system_instruction: str = "") -> Optional[Dict[str, Any]]:
        """Generate structured JSON response."""
        if self._provider == "gemini":
            try:
                full_prompt = f"{system_instruction}\n\nStrictly return valid JSON only:\n{prompt}"
                response = self._gemini_model.generate_content(
                    full_prompt,
                    generation_config={"response_mime_type": "application/json"}
                )
                return self._clean_and_parse_json(response.text)
            except Exception as e:
                print(f"[LLMClient] Gemini JSON error: {e}")

        elif self._provider == "openai":
            try:
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": f"{system_instruction}\nRespond in valid JSON."})
                messages.append({"role": "user", "content": prompt})

                response = self._openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
                return self._clean_and_parse_json(response.choices[0].message.content)
            except Exception as e:
                print(f"[LLMClient] OpenAI JSON error: {e}")

        return None

    def _clean_and_parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Clean markdown markers and parse JSON string safely."""
        if not text:
            return None
        cleaned = text.strip()
        # Remove ```json ... ```
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Fallback regex search for { ... }
            match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
        return None


# Global singleton instance
_llm_client_instance: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _llm_client_instance
    if _llm_client_instance is None:
        _llm_client_instance = LLMClient()
    return _llm_client_instance

