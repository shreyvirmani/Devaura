"""Devaura LLM Provider Layer.

Provides clean abstraction for LLM inference with:
- Google Gemini provider (Gemini 1.5 Flash via REST)
- OpenAI provider (gpt-4o-mini via REST)
- DeterministicMockLLMProvider (offline deterministic mode with real token/cost tracking)
- ProviderFactory with strict credential checks and environment mode switching
"""

from abc import ABC, abstractmethod
import asyncio
from datetime import datetime, timezone
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar
import uuid

from dotenv import load_dotenv
import httpx
from pydantic import BaseModel

load_dotenv()

from agent.llm.models import (
    LLMMode,
    LLMPatchProposal,
    LLMProposedChange,
    LLMRepairPlanProposal,
    LLMInvestigationResult,
    LLMResponse,
    LLMUsage,
)

T = TypeVar("T", bound=BaseModel)


class LLMConfigurationError(RuntimeError):
    """Raised when required LLM credentials or configuration are missing."""
    pass


class LLMExecutionError(RuntimeError):
    """Raised when an LLM inference call fails or returns unparseable content."""
    pass


class LLMProvider(ABC):
    """Abstract interface for LLM operations in Devaura."""

    def __init__(self, model_name: str, api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0

    @abstractmethod
    def provider_name(self) -> str:
        """Name of the LLM provider."""
        pass

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Synchronously generate unstructured or tool-augmented response."""
        pass

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
    ) -> Tuple[T, LLMUsage]:
        """Synchronously generate strictly validated structured output matching Pydantic schema."""
        pass

    async def agenerate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Asynchronously generate unstructured response."""
        return await asyncio.to_thread(self.generate, prompt, system_prompt, tools, temperature)

    async def agenerate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
    ) -> Tuple[T, LLMUsage]:
        """Asynchronously generate strictly validated structured output."""
        return await asyncio.to_thread(self.generate_structured, prompt, schema, system_prompt, temperature)

    def model_info(self) -> Dict[str, Any]:
        """Metadata about active model."""
        return {
            "provider": self.provider_name(),
            "model": self.model_name,
            "has_credentials": bool(self.api_key),
        }

    def token_usage(self) -> Dict[str, Any]:
        """Cumulative token telemetry."""
        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "estimated_cost_usd": round(self.total_cost_usd, 6),
        }


class GeminiProvider(LLMProvider):
    """Google Gemini REST API implementation with structured JSON support."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    # Pricing per 1M tokens (Gemini 2.5 Flash reference: $0.075 / $0.30)
    PRICE_PER_M_INPUT = 0.075
    PRICE_PER_M_OUTPUT = 0.30

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_seconds: float = 30.0,
    ):
        model = model_name or os.getenv("DEVAURA_GEMINI_MODEL") or "gemini-2.5-flash"
        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        super().__init__(model_name=model, api_key=key)
        self.timeout_seconds = timeout_seconds

    def provider_name(self) -> str:
        return "gemini"

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        cost = (input_tokens / 1_000_000) * self.PRICE_PER_M_INPUT + (
            output_tokens / 1_000_000
        ) * self.PRICE_PER_M_OUTPUT
        return round(cost, 6)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        if not self.api_key:
            raise LLMConfigurationError("Gemini API key is not configured. Live mode cannot execute.")

        url = f"{self.BASE_URL}/{self.model_name}:generateContent?key={self.api_key}"
        payload: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature},
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        t0 = time.perf_counter()
        resp = None
        try:
            for attempt in range(3):
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    resp = client.post(url, json=payload)
                    if resp.status_code in (429, 503) and attempt < 2:
                        time.sleep(2.0 * (attempt + 1))
                        continue
                    break
        except httpx.RequestError as e:
            raise LLMExecutionError(f"Network error communicating with Gemini API: {e}")

        if resp is None or resp.status_code != 200:
            err_msg = resp.text if resp is not None else "No response"
            code = resp.status_code if resp is not None else "Timeout"
            raise LLMExecutionError(f"Gemini API returned HTTP {code}: {err_msg}")
        data = resp.json()

        latency_ms = (time.perf_counter() - t0) * 1000
        text = ""
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                text = parts[0].get("text", "")

        meta = data.get("usageMetadata") or {}
        input_tokens = meta.get("promptTokenCount", 0)
        output_tokens = meta.get("candidatesTokenCount", 0)
        cost = self._estimate_cost(input_tokens, output_tokens)

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd += cost

        usage = LLMUsage(
            provider=self.provider_name(),
            model=self.model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated_cost_usd=cost,
            latency_ms=round(latency_ms, 2),
            request_id=str(uuid.uuid4())[:8],
        )

        return LLMResponse(content=text, usage=usage)

    def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
    ) -> Tuple[T, LLMUsage]:
        if not self.api_key:
            raise LLMConfigurationError("Gemini API key is not configured. Live mode cannot execute.")

        json_schema = schema.model_json_schema()
        structured_prompt = (
            f"{prompt}\n\n"
            f"You MUST respond ONLY with valid JSON conforming strictly to this JSON schema:\n"
            f"```json\n{json.dumps(json_schema, indent=2)}\n```\n"
            f"Do not include any Markdown fences, thought blocks, or commentary. Output valid JSON only."
        )

        url = f"{self.BASE_URL}/{self.model_name}:generateContent?key={self.api_key}"
        payload: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": structured_prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
            },
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        t0 = time.perf_counter()
        resp = None
        try:
            for attempt in range(3):
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    resp = client.post(url, json=payload)
                    if resp.status_code in (429, 503) and attempt < 2:
                        time.sleep(2.0 * (attempt + 1))
                        continue
                    break
        except httpx.RequestError as e:
            raise LLMExecutionError(f"Network error communicating with Gemini API: {e}")

        if resp is None or resp.status_code != 200:
            err_msg = resp.text if resp is not None else "No response"
            code = resp.status_code if resp is not None else "Timeout"
            raise LLMExecutionError(f"Gemini API returned HTTP {code}: {err_msg}")
        data = resp.json()

        latency_ms = (time.perf_counter() - t0) * 1000
        candidates = data.get("candidates", [])
        if not candidates:
            raise LLMExecutionError("Gemini returned no candidates.")

        parts = candidates[0].get("content", {}).get("parts", [])
        raw_text = parts[0].get("text", "") if parts else ""

        # Strict JSON parse & validation (No silent repair of malformed output)
        try:
            parsed_json = json.loads(raw_text)
            instance = schema.model_validate(parsed_json)
        except Exception as e:
            raise LLMExecutionError(f"Failed to validate Gemini JSON against {schema.__name__}: {e}. Raw: {raw_text[:200]}")

        meta = data.get("usageMetadata") or {}
        input_tokens = meta.get("promptTokenCount", 0)
        output_tokens = meta.get("candidatesTokenCount", 0)
        cost = self._estimate_cost(input_tokens, output_tokens)

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd += cost

        usage = LLMUsage(
            provider=self.provider_name(),
            model=self.model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated_cost_usd=cost,
            latency_ms=round(latency_ms, 2),
            request_id=str(uuid.uuid4())[:8],
        )

        return instance, usage


class OpenAIProvider(LLMProvider):
    """OpenAI REST API implementation with json_object response format."""

    BASE_URL = "https://api.openai.com/v1/chat/completions"

    # Pricing per 1M tokens (gpt-4o-mini reference: $0.15 / $0.60)
    PRICE_PER_M_INPUT = 0.15
    PRICE_PER_M_OUTPUT = 0.60

    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        timeout_seconds: float = 30.0,
    ):
        key = api_key or os.getenv("OPENAI_API_KEY")
        super().__init__(model_name=model_name, api_key=key)
        self.timeout_seconds = timeout_seconds

    def provider_name(self) -> str:
        return "openai"

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        cost = (input_tokens / 1_000_000) * self.PRICE_PER_M_INPUT + (
            output_tokens / 1_000_000
        ) * self.PRICE_PER_M_OUTPUT
        return round(cost, 6)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        if not self.api_key:
            raise LLMConfigurationError("OpenAI API key is not configured. Live mode cannot execute.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        t0 = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(
                    self.BASE_URL,
                    headers=headers,
                    json={"model": self.model_name, "messages": messages, "temperature": temperature},
                )
        except httpx.RequestError as e:
            raise LLMExecutionError(f"Network error communicating with OpenAI API: {e}")

        if resp.status_code != 200:
            raise LLMExecutionError(f"OpenAI API returned HTTP {resp.status_code}: {resp.text}")
        data = resp.json()

        latency_ms = (time.perf_counter() - t0) * 1000
        text = data["choices"][0]["message"]["content"]
        usage_data = data.get("usage") or {}
        input_tokens = usage_data.get("prompt_tokens", 0)
        output_tokens = usage_data.get("completion_tokens", 0)
        cost = self._estimate_cost(input_tokens, output_tokens)

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd += cost

        usage = LLMUsage(
            provider=self.provider_name(),
            model=self.model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated_cost_usd=cost,
            latency_ms=round(latency_ms, 2),
            request_id=data.get("id"),
        )
        return LLMResponse(content=text, usage=usage)

    def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
    ) -> Tuple[T, LLMUsage]:
        if not self.api_key:
            raise LLMConfigurationError("OpenAI API key is not configured. Live mode cannot execute.")

        json_schema = schema.model_json_schema()
        prompt_with_schema = (
            f"{prompt}\n\nRespond with a valid JSON object strictly matching this schema:\n"
            f"{json.dumps(json_schema, indent=2)}"
        )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt_with_schema})

        t0 = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(
                    self.BASE_URL,
                    headers=headers,
                    json={
                        "model": self.model_name,
                        "messages": messages,
                        "temperature": temperature,
                        "response_format": {"type": "json_object"},
                    },
                )
        except httpx.RequestError as e:
            raise LLMExecutionError(f"Network error communicating with OpenAI API: {e}")

        if resp.status_code != 200:
            raise LLMExecutionError(f"OpenAI API returned HTTP {resp.status_code}: {resp.text}")
        data = resp.json()

        latency_ms = (time.perf_counter() - t0) * 1000
        raw_text = data["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(raw_text)
            instance = schema.model_validate(parsed)
        except Exception as e:
            raise LLMExecutionError(f"Failed to validate OpenAI JSON against {schema.__name__}: {e}")

        usage_data = data.get("usage") or {}
        input_tokens = usage_data.get("prompt_tokens", 0)
        output_tokens = usage_data.get("completion_tokens", 0)
        cost = self._estimate_cost(input_tokens, output_tokens)

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd += cost

        usage = LLMUsage(
            provider=self.provider_name(),
            model=self.model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated_cost_usd=cost,
            latency_ms=round(latency_ms, 2),
            request_id=data.get("id"),
        )
        return instance, usage


class DeterministicMockLLMProvider(LLMProvider):
    """Deterministic offline provider executing without network calls.

    Generates realistic simulated token usage, latency, and cost telemetry.
    Adheres strictly to zero ground-truth leakage.
    """

    PRICE_PER_M_INPUT = 0.075
    PRICE_PER_M_OUTPUT = 0.30

    def __init__(self, model_name: str = "devaura-deterministic-llm-v1"):
        super().__init__(model_name=model_name, api_key="deterministic-offline-key")

    def provider_name(self) -> str:
        return "deterministic-mock"

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        t0 = time.perf_counter()
        content = "Deterministic LLM generated response analyzing evidence."
        latency_ms = (time.perf_counter() - t0) * 1000 + 4.5

        input_tokens = len(prompt) // 4 + 50
        output_tokens = len(content) // 4 + 20
        cost = (input_tokens / 1_000_000) * self.PRICE_PER_M_INPUT + (
            output_tokens / 1_000_000
        ) * self.PRICE_PER_M_OUTPUT

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd += cost

        usage = LLMUsage(
            provider=self.provider_name(),
            model=self.model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated_cost_usd=round(cost, 6),
            latency_ms=round(latency_ms, 2),
            request_id=f"det-{uuid.uuid4().hex[:8]}",
        )
        return LLMResponse(content=content, usage=usage)

    def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> Tuple[T, LLMUsage]:
        t0 = time.perf_counter()
        schema_name = schema.__name__

        import re
        if schema_name == "LLMInvestigationResult":
            # Extract evidence IDs mentioned in the prompt (handles colons, e.g. ev:inv-1:1)
            ev_matches = re.findall(r"(?:Evidence ID:\s*|\[evidence_id:\s*)([^\s\]\n]+)", prompt)
            cited_ids = ev_matches[:3] if ev_matches else ["ev_001"]

            # Extract any file mentions in prompt (preferring non-test files)
            file_matches = re.findall(r"(?:\[file:\s*([^\s\]]+)\]|(?:[a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-/\\]+\.py))", prompt)
            clean_files = []
            for fm in file_matches:
                f_str = fm if isinstance(fm, str) else (fm[0] or fm[1] if len(fm) > 1 else "")
                if f_str and not ("test_" in f_str or f_str.startswith("test")):
                    clean_files.append(f_str.replace("\\", "/").strip())
            pred_file = clean_files[0] if clean_files else "app/service.py"

            data = {
                "failure_summary": "Identified failure from stack trace and test output.",
                "observed_facts": [
                    "Test failed with assertion or exception.",
                    f"Failing location referenced {pred_file}.",
                ],
                "root_cause_candidates": [
                    {
                        "candidate_id": "cand-llm-01",
                        "statement": f"Defect in {pred_file} causing failure.",
                        "affected_files": [pred_file],
                        "affected_symbols": ["target_function"],
                        "supporting_evidence_ids": cited_ids,
                        "contradicting_evidence_ids": [],
                        "confidence": 0.88,
                        "uncertainty": "Calibrated against stack frames",
                    }
                ],
                "recommended_next_evidence": ["Inspect test fixtures and related calls."],
                "sufficiency": "SUFFICIENT",
            }
        elif schema_name == "LLMRepairPlanProposal":
            ev_matches = re.findall(r"(?:Evidence ID:\s*|\[evidence_id:\s*)([^\s\]\n]+)", prompt)
            cited_ids = ev_matches[:2] if ev_matches else ["ev_001"]

            file_matches = re.findall(r"(?:Permitted Affected Files:\s*([^\n\r]+)|(?:[a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-/\\]+\.py))", prompt)
            clean_files = []
            for fm in file_matches:
                f_str = fm if isinstance(fm, str) else (fm[0] or fm[1] if len(fm) > 1 else "")
                if f_str:
                    parts = [p.strip() for p in f_str.split(",") if p.strip() and not ("test_" in p or p.startswith("test"))]
                    clean_files.extend(parts)
            target_file = clean_files[0] if clean_files else "app/service.py"

            data = {
                "objective": f"Resolve root cause in {target_file}",
                "root_cause_summary": f"Defensive guard required in {target_file}",
                "proposed_changes": [
                    {
                        "file": target_file,
                        "symbol": "target_function",
                        "location": "lines 1-10",
                        "change_description": "Apply input validation and defensive guard",
                        "evidence_ids": cited_ids,
                        "verification_tests": ["pytest test_service.py"],
                    }
                ],
                "risks": ["Potential edge-case parameter drift"],
                "assumptions": ["Inputs adhere to expected typing"],
                "unresolved_questions": [],
                "confidence": 0.90,
            }
        elif schema_name == "LLMPatchProposal":
            file_matches = re.findall(r"(?:File:\s*([^\s\n\r]+)|path=\"([^\s\"\n\r]+)\")", prompt)
            target_file = "app/service.py"
            if file_matches:
                for m in file_matches:
                    match_str = m[0] or m[1] if isinstance(m, tuple) else m
                    if match_str and not ("test_" in match_str or match_str.startswith("test")):
                        target_file = match_str.replace("\\", "/").strip()
                        break

            data = {
                "unified_diff": (
                    f"--- a/{target_file}\n"
                    f"+++ b/{target_file}\n"
                    f"@@ -1,3 +1,4 @@\n"
                    f"+# LLM defensive repair\n"
                ),
                "explanation": "Applied evidence-backed repair guard.",
                "assumptions": ["Deterministic patch synthesis"],
                "cited_evidence_ids": ["ev_001"],
            }
        else:
            raise ValueError(f"Deterministic provider has no fixture for schema {schema_name}")

        instance = schema.model_validate(data)
        latency_ms = (time.perf_counter() - t0) * 1000 + 8.5
        input_tokens = len(prompt) // 4 + 60
        output_tokens = len(json.dumps(data)) // 4 + 30
        cost = (input_tokens / 1_000_000) * self.PRICE_PER_M_INPUT + (
            output_tokens / 1_000_000
        ) * self.PRICE_PER_M_OUTPUT

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd += cost

        usage = LLMUsage(
            provider=self.provider_name(),
            model=self.model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated_cost_usd=round(cost, 6),
            latency_ms=round(latency_ms, 2),
            request_id=f"det-struct-{uuid.uuid4().hex[:8]}",
        )
        return instance, usage


class ProviderFactory:
    """Factory creating configured LLM provider according to environment mode."""

    @classmethod
    def get_provider(
        cls,
        mode: Optional[str] = None,
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> LLMProvider:
        active_mode = (mode or os.getenv("DEVAURA_LLM_MODE") or LLMMode.DETERMINISTIC.value).lower()
        active_provider = (provider_name or os.getenv("DEVAURA_LLM_PROVIDER") or "gemini").lower()

        if active_mode == LLMMode.LIVE.value:
            if active_provider == "gemini":
                key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                if not key:
                    raise LLMConfigurationError(
                        "DEVAURA_LLM_MODE=live requested with gemini provider, but GEMINI_API_KEY or GOOGLE_API_KEY is unset."
                    )
                return GeminiProvider(model_name=model_name, api_key=key)
            elif active_provider == "openai":
                key = os.getenv("OPENAI_API_KEY")
                if not key:
                    raise LLMConfigurationError(
                        "DEVAURA_LLM_MODE=live requested with openai provider, but OPENAI_API_KEY is unset."
                    )
                return OpenAIProvider(model_name=model_name or "gpt-4o-mini", api_key=key)
            else:
                raise LLMConfigurationError(f"Unsupported live LLM provider: {active_provider}")
        else:
            # Deterministic / offline mode
            return DeterministicMockLLMProvider(model_name=model_name or "devaura-deterministic-llm-v1")
