"""
StateAsserter — part of repair logic, not the normal execution path.

When the executor fails, the repair service can call the asserter to reason:
"Given the milestone and the current state (which already contains task,
parent_task, and all execution outputs) — was the milestone achieved?"

state always contains:
  task        — the original task description
  parent_task — set for subtask calls, absent for top-level
  + all keys written by tools during execution

The asserter only needs state + milestone. Everything else is in state.
"""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
import requests


class AssertResult(BaseModel):
    ok: bool
    reason: str


class StateAsserter:
    def __init__(self, base_url: str):
        self._url = f"{base_url.rstrip('/')}/assert_milestone"

    def check(self, milestone: list[str], state: dict[str, Any]) -> AssertResult:
        resp = requests.post(self._url, json={"milestone": milestone, "state": state})
        resp.raise_for_status()
        return AssertResult(**resp.json())
