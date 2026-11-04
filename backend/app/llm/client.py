"""
Provider-agnostic LLM client supporting Gemini and OpenAI.
Provides structured JSON generation, free-text generation, and function-calling
intent classification for the orchestrator agent.
"""
import json
import re
from typing import Dict, Any, Optional, List
from ..config import settings


# Tool schemas exposed to the LLM for intent classification via function calling.
ORCHESTRATOR_TOOLS = [
    {
        "name": "recommend_jobs",
        "description": (
            "Search the job dataset and recommend matching positions. Call this "
            "when the user wants to see jobs, asks for recommendations, refines "
            "filters (remote, skills, experience), or mentions a company/role."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "remote": {
                    "type": "boolean",
                    "description": "True for remote-only, False for onsite-only, omit for no preference.",
                },
                "skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific tech skills to filter by (e.g. ['React', 'Python']).",
                },
                "max_experience": {
                    "type": "integer",
                    "description": "Maximum years of experience the candidate wants (e.g. 1 for fresher/intern).",
                },
                "source": {
                    "type": "string",
                    "description": "Job source platform: 'LinkedIn', 'Arbeitnow', 'Remotive', or 'Jobfound'.",
                },
                "company": {
                    "type": "string",
                    "description": "Specific company name to filter by.",
                },
                "query": {
                    "type": "string",
                    "description": "Role or title keyword (e.g. 'backend', 'SDE', 'full stack', 'devops').",
                },
            },
        },
    },
    {
        "name": "apply_to_job",
        "description": (
            "Apply to a specific job by its display number from the last "
            "recommendation list. Call when the user says things like "
            "'apply to job 3' or 'submit application for the second one'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "job_number": {
                    "type": "string",
                    "description": "The job reference number or index from the displayed results.",
                },
            },
            "required": ["job_number"],
        },
    },
    {
        "name": "list_applications",
        "description": (
            "List all jobs the user has previously applied to and their current "
            "status. Call when user asks about applied jobs, application status, "
            "or tracking."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "greet_user",
        "description": (
            "Respond to a greeting, help request, or general question about "
            "what the assistant can do. Call for 'hi', 'hello', 'help', 'what "
            "can you do', etc."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "reset_filters",
        "description": (
            "Reset all active search filters back to defaults. Call when user "
            "says 'reset', 'clear filters', 'start over', or 'show all jobs'."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "next_page",
        "description": (
            "Load the next page of job results. Call when user says 'show more', "
            "'next', 'more jobs', 'next page', 'load more'."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
]


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

    # ------------------------------------------------------------------
    # Function-calling intent classification for the orchestrator agent
    # ------------------------------------------------------------------
    def classify_intent(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        system_prompt: str,
    ) -> Optional[Dict[str, Any]]:
        """Use LLM function calling to classify the user's intent.

        Returns a dict like ``{"tool": "recommend_jobs", "args": {"remote": True}}``
        or ``None`` if the provider is unavailable (caller should use regex fallback).
        """
        if self._provider == "gemini":
            return self._classify_gemini(user_message, conversation_history, system_prompt)
        elif self._provider == "openai":
            return self._classify_openai(user_message, conversation_history, system_prompt)
        return None

    def _classify_gemini(
        self, user_message: str, history: List[Dict[str, str]], system_prompt: str
    ) -> Optional[Dict[str, Any]]:
        try:
            import google.generativeai as genai

            # Build Gemini tool declarations
            tool_declarations = []
            for t in ORCHESTRATOR_TOOLS:
                tool_declarations.append(
                    genai.protos.FunctionDeclaration(
                        name=t["name"],
                        description=t["description"],
                        parameters=t["parameters"],
                    )
                )

            tool_config = genai.protos.ToolConfig(
                function_calling_config=genai.protos.FunctionCallingConfig(
                    mode=genai.protos.FunctionCallingConfig.Mode.ANY
                )
            )

            model = genai.GenerativeModel(
                "gemini-1.5-flash",
                system_instruction=system_prompt,
                tools=[genai.protos.Tool(function_declarations=tool_declarations)],
                tool_config=tool_config,
            )

            # Build chat history for context
            gemini_history = []
            for msg in history[-10:]:  # Last 10 messages for context
                role = "user" if msg["role"] == "user" else "model"
                gemini_history.append({"role": role, "parts": [msg["content"]]})

            chat = model.start_chat(history=gemini_history)
            response = chat.send_message(user_message)

            # Extract the function call
            candidate = response.candidates[0]
            for part in candidate.content.parts:
                if hasattr(part, "function_call") and part.function_call.name:
                    fc = part.function_call
                    args = dict(fc.args) if fc.args else {}
                    # Convert protobuf values to Python natives
                    clean_args = {}
                    for k, v in args.items():
                        if hasattr(v, "string_value"):
                            clean_args[k] = v
                        elif isinstance(v, (str, int, float, bool)):
                            clean_args[k] = v
                        elif isinstance(v, list):
                            clean_args[k] = list(v)
                        else:
                            clean_args[k] = v
                    return {"tool": fc.name, "args": clean_args}

        except Exception as e:
            print(f"[LLMClient] Gemini function-calling error: {e}")
        return None

    def _classify_openai(
        self, user_message: str, history: List[Dict[str, str]], system_prompt: str
    ) -> Optional[Dict[str, Any]]:
        try:
            messages = [{"role": "system", "content": system_prompt}]
            for msg in history[-10:]:
                messages.append({"role": msg["role"], "content": msg["content"]})
            messages.append({"role": "user", "content": user_message})

            openai_tools = []
            for t in ORCHESTRATOR_TOOLS:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["parameters"],
                    },
                })

            response = self._openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                tools=openai_tools,
                tool_choice="required",
                temperature=0.0,
            )

            tool_call = response.choices[0].message.tool_calls
            if tool_call:
                fc = tool_call[0].function
                return {
                    "tool": fc.name,
                    "args": json.loads(fc.arguments) if fc.arguments else {},
                }
        except Exception as e:
            print(f"[LLMClient] OpenAI function-calling error: {e}")
        return None

    # ------------------------------------------------------------------
    # Text and JSON generation (existing functionality)
    # ------------------------------------------------------------------
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
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
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
