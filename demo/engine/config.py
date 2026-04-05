from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class EngineConfig:
    model: str = "qwen2.5:7b"
    ollama_url: str = "http://localhost:11434"
    timeout: int = 60
