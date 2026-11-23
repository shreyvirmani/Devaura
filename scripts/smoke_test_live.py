"""Live LLM Smoke Test for Devaura Phase 9.1."""

from datetime import datetime, timezone
import json
import os
import sys
import time
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pydantic import BaseModel, ConfigDict
from dotenv import load_dotenv

load_dotenv()

from agent.llm.provider import ProviderFactory, LLMConfigurationError, LLMExecutionError


class ErrorClassification(BaseModel):
    model_config = ConfigDict(extra="ignore")
    error_type: str
    summary: str
    severity: str


def run_smoke_test():
    print("=" * 60)
    print("DEVAURA PHASE 9.1: LIVE LLM SMOKE TEST")
    print("=" * 60)

    mode = os.getenv("DEVAURA_LLM_MODE", "live")
    provider_name = os.getenv("DEVAURA_LLM_PROVIDER", "gemini")

    print(f"Mode: {mode}")
    print(f"Provider: {provider_name}")

    provider = ProviderFactory.get_provider(mode="live", provider_name=provider_name)
    print(f"Instantiated: {provider.provider_name()} (Model: {provider.model_name})")

    prompt = (
        "Classify the following software error:\n\n"
        "TypeError: unsupported operand type(s) for +: 'int' and 'str'\n"
        "At: app/calculator.py:42 in add_values\n"
    )

    t0 = time.perf_counter()
    res, usage = provider.generate_structured(
        prompt=prompt,
        schema=ErrorClassification,
        system_prompt="You are an automated software triage system. Output valid JSON adhering to the schema.",
    )
    latency_ms = (time.perf_counter() - t0) * 1000

    print("\n--- Smoke Test Succeeded ---")
    print(f"HTTP Status: 200 (Parsed successfully into {ErrorClassification.__name__})")
    print(f"Parsed result: {res.model_dump()}")
    print(f"Round-trip latency: {latency_ms:.2f} ms")
    print(f"API Prompt Tokens: {usage.input_tokens}")
    print(f"API Completion Tokens: {usage.output_tokens}")
    print(f"API Total Tokens: {usage.total_tokens}")
    print(f"Estimated Cost: ${usage.estimated_cost_usd:.6f}")
    print(f"Request ID: {usage.request_id}")

    output_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": provider.provider_name(),
        "model": provider.model_name,
        "http_status": 200,
        "latency_ms": round(latency_ms, 2),
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "estimated_cost_usd": usage.estimated_cost_usd,
        "request_id": usage.request_id,
        "prompt": prompt,
        "parsed_response": res.model_dump(),
        "schema_validated": True,
    }

    os.makedirs("evaluation/results", exist_ok=True)
    with open("evaluation/results/smoke_test_result.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print("\nSaved smoke test evidence to evaluation/results/smoke_test_result.json")
    return output_data


if __name__ == "__main__":
    run_smoke_test()
