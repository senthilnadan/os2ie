from __future__ import annotations
from typing import Any
import requests
from .models import AbstractDSTT, AbstractTransition, ExecutableDSTT


class Task2PlanClient:
    def __init__(self, base_url: str):
        self._url = f"{base_url.rstrip('/')}/as_task2plan"

    def plan(self, task: str) -> tuple[AbstractDSTT, dict[str, Any]]:
        resp = requests.post(self._url, json={"user_task": task})
        resp.raise_for_status()
        data = resp.json()
        return AbstractDSTT(**data["abstract_dstt"]), data.get("meta", {})


class Transition2ExecClient:
    def __init__(self, base_url: str):
        self._url = f"{base_url.rstrip('/')}/transition2exec"

    def compile(
        self,
        task: str,
        state: dict[str, Any],
        abstract_transition: AbstractTransition,
        available_tools: list[dict[str, Any]] | None = None,
    ) -> tuple[ExecutableDSTT, dict[str, Any]]:
        """
        Compile an abstract transition into an executable transition.

        available_tools is injected by the caller (provider/agent upstream).
        If not provided, an empty list is sent — the server must have its own
        fallback or the call will fail.
        """
        resp = requests.post(
            self._url,
            json={
                "task": task,
                "context": state,
                "abstract_transition": abstract_transition.model_dump(),
                "available_tools": available_tools or [],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return ExecutableDSTT(**data["executable_dstt"]), data.get("meta", {})
