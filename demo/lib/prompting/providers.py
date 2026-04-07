from __future__ import annotations
import requests


class OllamaProvider:
    """Ollama local model provider."""

    def __init__(self, model: str, url: str = "http://localhost:11434", timeout: int = 60) -> None:
        self._model = model
        self._url = url
        self._timeout = timeout

    def __call__(self, prompt: str) -> str:
        resp = requests.post(
            f"{self._url}/api/generate",
            json={"model": self._model, "prompt": prompt, "stream": False},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()["response"].strip()


class ChatAPIProvider:
    """OpenAI-compatible Chat API provider."""

    def __init__(self, model: str, api_key: str, base_url: str = "https://api.openai.com/v1",
                 timeout: int = 60) -> None:
        self._model = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def __call__(self, prompt: str) -> str:
        resp = requests.post(
            f"{self._base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self._model, "messages": [{"role": "user", "content": prompt}]},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
