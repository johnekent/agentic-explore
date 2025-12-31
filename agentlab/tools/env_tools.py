from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import requests

from agentlab.core.config import get_setting
from agentlab.db.db import connect
from agentlab.providers.llm import HeuristicLLM, OllamaLLM, get_provider
from agentlab.tools.types import ToolResult


def env_check_db(db_path: str, min_free_mb: int = 50) -> ToolResult:
    try:
        path = Path(db_path)
        if not path.exists():
            return ToolResult.failure("db_missing", "Database file not found.", {"db_path": str(path)})

        usage = shutil.disk_usage(str(path.parent))
        free_mb = int(usage.free / (1024 * 1024))
        if free_mb < min_free_mb:
            return ToolResult.failure(
                "low_disk_space",
                "Insufficient free disk space.",
                {"free_mb": free_mb, "min_free_mb": min_free_mb},
            )

        con = connect(path)
        con.execute("SELECT 1")
        con.close()
        return ToolResult.success({"db_path": str(path), "free_mb": free_mb})
    except Exception as exc:
        return ToolResult.failure("db_check_error", str(exc))


def _start_ollama() -> tuple[bool, str | None]:
    exe = shutil.which("ollama")
    if not exe:
        return False, "ollama not found in PATH"
    try:
        kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        subprocess.Popen([exe, "serve"], **kwargs)
        return True, None
    except Exception as exc:
        return False, str(exc)


def _start_ollama_docker(base_url: str) -> tuple[bool, str | None]:
    if not base_url.startswith(("http://localhost", "http://127.0.0.1")):
        return False, "base_url is not localhost; docker auto-start skipped"
    exe = shutil.which("docker")
    if not exe:
        return False, "docker not found in PATH"
    try:
        result = subprocess.run(
            [exe, "ps", "-a", "--filter", "name=^/ollama$", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        names = {n.strip() for n in result.stdout.splitlines() if n.strip()}
        if "ollama" in names:
            subprocess.run([exe, "start", "ollama"], capture_output=True, text=True, check=False, timeout=10)
        else:
            subprocess.run(
                [exe, "run", "-d", "--name", "ollama", "-p", "11434:11434", "ollama/ollama"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        return True, None
    except Exception as exc:
        return False, str(exc)


def env_check_llm(timeout_s: int = 2, auto_start: bool = False, start_wait_s: int = 2) -> ToolResult:
    try:
        attempts: list[dict[str, str]] = []
        provider = get_provider()
        if isinstance(provider, HeuristicLLM):
            return ToolResult.success({"provider": "heuristic", "ready": False, "attempts": attempts})
        if isinstance(provider, OllamaLLM):
            base_url = provider.base_url.rstrip("/")
            try:
                r = requests.get(f"{base_url}/api/tags", timeout=timeout_s)
                r.raise_for_status()
            except Exception as exc:
                attempts.append({"step": "ollama_ping", "error": str(exc)})
                if auto_start:
                    started, start_err = _start_ollama()
                    if not started:
                        attempts.append({"step": "ollama_start", "error": str(start_err)})
                        docker_started, docker_err = _start_ollama_docker(base_url)
                        if not docker_started:
                            attempts.append({"step": "ollama_docker_start", "error": str(docker_err)})
                            return ToolResult.failure(
                                "llm_start_failed",
                                "Failed to start Ollama.",
                                {
                                    "base_url": base_url,
                                    "error": str(exc),
                                    "start_error": start_err,
                                    "docker_error": docker_err,
                                    "attempts": attempts,
                                },
                            )
                        attempts.append({"step": "ollama_docker_start", "error": ""})
                        time.sleep(max(0, start_wait_s))
                        try:
                            retry = requests.get(f"{base_url}/api/tags", timeout=timeout_s)
                            retry.raise_for_status()
                        except Exception as retry_exc:
                            attempts.append({"step": "ollama_docker_ping", "error": str(retry_exc)})
                            return ToolResult.failure(
                                "llm_unreachable",
                                "Ollama not reachable at base URL after docker start.",
                                {"base_url": base_url, "error": str(retry_exc), "attempts": attempts},
                            )
                        return ToolResult.success(
                            {
                                "provider": "ollama",
                                "ready": True,
                                "base_url": base_url,
                                "model": provider.model,
                                "started": True,
                                "started_via": "docker",
                                "attempts": attempts,
                            }
                        )
                    time.sleep(max(0, start_wait_s))
                    try:
                        retry = requests.get(f"{base_url}/api/tags", timeout=timeout_s)
                        retry.raise_for_status()
                    except Exception as retry_exc:
                        attempts.append({"step": "ollama_start_ping", "error": str(retry_exc)})
                        return ToolResult.failure(
                            "llm_unreachable",
                            "Ollama not reachable at base URL after start.",
                            {"base_url": base_url, "error": str(retry_exc), "attempts": attempts},
                        )
                    return ToolResult.success(
                        {
                            "provider": "ollama",
                            "ready": True,
                            "base_url": base_url,
                            "model": provider.model,
                            "started": True,
                            "attempts": attempts,
                        }
                    )
                return ToolResult.failure(
                    "llm_unreachable",
                    "Ollama not reachable at base URL.",
                    {"base_url": base_url, "error": str(exc), "attempts": attempts},
                )
            try:
                data = r.json()
            except Exception:
                data = {}
            models = data.get("models") or []
            model_names = [m.get("name") for m in models if isinstance(m, dict)]
            if provider.model:
                exact = provider.model in model_names
                tagged = any(name.startswith(f"{provider.model}:") for name in model_names if name)
                if not exact and not tagged:
                    return ToolResult.failure(
                        "llm_model_missing",
                        "Ollama model not found. Pull the model first.",
                        {"model": provider.model, "available": model_names},
                    )
            return ToolResult.success(
                {"provider": "ollama", "ready": True, "base_url": base_url, "model": provider.model, "attempts": attempts}
            )
        return ToolResult.failure("llm_unknown", "Unknown LLM provider.", {"provider": type(provider).__name__})
    except Exception as exc:
        return ToolResult.failure("llm_check_error", str(exc))
