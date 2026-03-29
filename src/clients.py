from __future__ import annotations
from typing import Any
import requests
from .models import AbstractDSTT, AbstractTransition, ExecutableDSTT, Transition2ShellResult


class Task2PlanClient:
    def __init__(self, base_url: str):
        self._url = f"{base_url.rstrip('/')}/task2plan"

    def plan(self, task: str, context: str = "", constraints: dict | None = None) -> tuple[AbstractDSTT, dict[str, Any]]:
        resp = requests.post(self._url, json={
            "task": task,
            "context": context,
            "constraints": constraints or {},
        })
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
        strategy: str = "input_first",
    ) -> tuple[ExecutableDSTT, dict[str, Any]]:
        """
        Compile an abstract transition into an executable transition.

        available_tools is injected by the caller (provider/agent upstream).
        If not provided, an empty list is sent — the server must have its own
        fallback or the call will fail.

        strategy: "input_first" (default), "output_first", or "scored"
        """
        resp = requests.post(
            self._url,
            json={
                "task": task,
                "context": state,
                "abstract_transition": abstract_transition.model_dump(),
                "available_tools": available_tools or [],
                "strategy": strategy,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return ExecutableDSTT(**data["executable_dstt"]), data.get("meta", {})


class Transition2ShellClient:
    def __init__(self, base_url: str):
        self._url = f"{base_url.rstrip('/')}/transition2Shell"

    def compile(
        self,
        task: str,
        intent: str,
        inputs: list[str],
        outputs: list[str],
        context: dict[str, Any],
    ) -> Transition2ShellResult:
        """
        Assess whether the intent can be implemented as a shell script and,
        if so, return a script_description. Assembly of the ExecutableTransition
        is the caller's (CreateTransitionHandler's) responsibility.
        """
        resp = requests.post(
            self._url,
            json={
                "task": task,
                "intent": intent,
                "inputs": inputs,
                "outputs": outputs,
                "context": context,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return Transition2ShellResult(**data.get("result", data))
