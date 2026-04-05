from __future__ import annotations
from typing import Any
from .model_client import call_model
from .config import EngineConfig


def ask(state: dict[str, Any], config: EngineConfig) -> dict[str, Any]:
    """Send a raw prompt to the model."""
    response = call_model(state["prompt"], config)
    return {"response": response}


def asktemplate(state: dict[str, Any], config: EngineConfig) -> dict[str, Any]:
    """Resolve {{key}} placeholders in template from state, send to model."""
    template = state["template"]
    prompt = template
    for key, val in state.items():
        if not key.startswith("_"):
            prompt = prompt.replace(f"{{{{{key}}}}}", str(val))
    response = call_model(prompt, config)
    return {"response": response}
