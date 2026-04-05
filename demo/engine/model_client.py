from __future__ import annotations
import requests
from .config import EngineConfig


def call_model(prompt: str, config: EngineConfig) -> str:
    resp = requests.post(
        f"{config.ollama_url}/api/generate",
        json={"model": config.model, "prompt": prompt, "stream": False},
        timeout=config.timeout,
    )
    resp.raise_for_status()
    return resp.json()["response"].strip()
