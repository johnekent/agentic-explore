from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import os
import requests
from agentlab.core.config import get_setting

@dataclass
class LLMResult:
    text: str
    raw: Any | None = None

class LLMProvider:
    def complete(self, system: str, user: str, temperature: float = 0.2) -> LLMResult:
        raise NotImplementedError

class HeuristicLLM(LLMProvider):
    def complete(self, system: str, user: str, temperature: float = 0.2) -> LLMResult:
        return LLMResult(text="(heuristic mode) No LLM configured. Set AGENTLAB_LLM=ollama for local scoring.")

class OllamaLLM(LLMProvider):
    def __init__(self):
        self.base_url = get_setting("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = get_setting("OLLAMA_MODEL", "llama3.1")
        try:
            self.timeout_s = int(get_setting("OLLAMA_TIMEOUT_S", "300"))
        except ValueError:
            self.timeout_s = 120

    def complete(self, system: str, user: str, temperature: float = 0.2) -> LLMResult:
        def _post(path: str, payload: dict[str, Any]) -> requests.Response:
            return requests.post(f"{self.base_url}{path}", json=payload, timeout=self.timeout_s)

        def _maybe_model_error(resp: requests.Response) -> str | None:
            try:
                data = resp.json()
            except Exception:
                data = {}
            err = str(data.get("error") or "")
            if "model" in err.lower():
                return err
            return None

        attempts: list[str] = []

        chat_payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"temperature": temperature},
            "stream": False,
        }
        attempts.append("/api/chat")
        r = _post("/api/chat", chat_payload)
        if r.status_code != 404:
            r.raise_for_status()
            data = r.json()
            content = data.get("message", {}).get("content", "")
            return LLMResult(text=content, raw=data)
        model_err = _maybe_model_error(r)
        if model_err:
            raise RuntimeError(model_err)

        gen_payload = {
            "model": self.model,
            "prompt": user,
            "system": system,
            "options": {"temperature": temperature},
            "stream": False,
        }
        attempts.append("/api/generate")
        r = _post("/api/generate", gen_payload)
        if r.status_code != 404:
            r.raise_for_status()
            data = r.json()
            content = data.get("response", "")
            return LLMResult(text=content, raw=data)
        model_err = _maybe_model_error(r)
        if model_err:
            raise RuntimeError(model_err)

        # OpenAI-compatible fallback
        openai_chat_payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
        }
        attempts.append("/v1/chat/completions")
        r = _post("/v1/chat/completions", openai_chat_payload)
        if r.status_code != 404:
            r.raise_for_status()
            data = r.json()
            choices = data.get("choices") or []
            content = ""
            if choices:
                content = choices[0].get("message", {}).get("content") or ""
            return LLMResult(text=content, raw=data)

        openai_comp_payload = {"model": self.model, "prompt": user, "temperature": temperature}
        attempts.append("/v1/completions")
        r = _post("/v1/completions", openai_comp_payload)
        if r.status_code != 404:
            r.raise_for_status()
            data = r.json()
            choices = data.get("choices") or []
            content = choices[0].get("text", "") if choices else ""
            return LLMResult(text=content, raw=data)

        raise RuntimeError(f"No supported LLM endpoint found. Tried: {', '.join(attempts)}")

def get_provider() -> LLMProvider:
    mode = (get_setting("AGENTLAB_LLM") or "").strip().lower()
    if mode == "ollama":
        return OllamaLLM()
    return HeuristicLLM()
