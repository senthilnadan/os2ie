"""
Regression suite for transition2exec — multi-tool baseline (17 seeds) + stress tests (20 seeds).

Requires a live transition2exec endpoint at http://127.0.0.1:8000/transition2exec.
Tests are automatically skipped if the endpoint is not reachable.

Pass criteria per seed:
  - not_mappable seeds: response status == "not_mappable"
  - all others: status == "ok", tool == expected["tool"], inputs == expected["inputs"]

Run baseline only:
    pytest tests/test_transition2exec_regression.py -v -m "not stress"

Run stress only:
    pytest tests/test_transition2exec_regression.py -v -m stress

Run all:
    pytest tests/test_transition2exec_regression.py -v
"""
from __future__ import annotations

import json
import pathlib
import pytest
import requests

from src.catalog import build_catalog

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ENDPOINT = "http://127.0.0.1:8000/transition2exec"
SEEDS_PATH = pathlib.Path(__file__).parent.parent / "training" / "transition2exec_seed.json"
STRESS_SEEDS_PATH = pathlib.Path(__file__).parent.parent / "training" / "transition2exec_stress_seed.json"
NOT_MAPPABLE_IDS = {"06", "07", "08", "12a", "15"}
STRESS_NOT_MAPPABLE_IDS = {
    "s12", "s13",                               # run_shell_command not in catalog
    "s14", "s15", "s17", "s18", "s19", "s20",  # genuinely not_mappable
}

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _endpoint_available() -> bool:
    try:
        requests.get(ENDPOINT, timeout=2)
        return True
    except requests.exceptions.ConnectionError:
        return False


def _load_seeds() -> list[dict]:
    data = json.loads(SEEDS_PATH.read_text())
    return data["seeds"]


def _load_stress_seeds() -> list[dict]:
    data = json.loads(STRESS_SEEDS_PATH.read_text())
    return data["seeds"]


def _call_transition2exec(seed: dict, available_tools: list[dict]) -> dict:
    payload = {
        "task": seed["task"],
        "context": seed["context"],
        "abstract_transition": seed["abstract_transition"],
        "available_tools": available_tools,
    }
    resp = requests.post(ENDPOINT, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _parse_response(response: dict) -> tuple[str, str, dict]:
    """Return (status, tool, inputs) from any known response envelope.

    Supported shapes:
      • {"executable_dstt": {"status": ..., "segments": [{"transitions": [...]}]}, "meta": {...}}
      • {"status": "...", "tool": "...", "inputs": {...}}
      • {"status": "...", "transitions": [...]}
    """
    # Shape 1 — executable_dstt envelope (current server format)
    if "executable_dstt" in response:
        dstt = response["executable_dstt"]
        status = dstt.get("status", "")
        if status == "not_mappable":
            return status, "not_mappable", {}
        for seg in dstt.get("segments", []):
            for t in seg.get("transitions", []):
                return status, t.get("tool", ""), t.get("inputs", {})
        return status, "", {}

    # Shape 2 — flat response
    if "tool" in response:
        return response.get("status", ""), response["tool"], response.get("inputs", {})

    # Shape 3 — transitions list
    transitions = response.get("transitions") or []
    if transitions:
        t = transitions[0]
        return response.get("status", ""), t.get("tool", ""), t.get("inputs", {})

    if response.get("status") == "not_mappable":
        return "not_mappable", "not_mappable", {}

    return response.get("status", ""), "", {}


# ---------------------------------------------------------------------------
# Parametrized regression tests
# ---------------------------------------------------------------------------

_seeds = _load_seeds()
_seed_ids = [s["id"] for s in _seeds]


@pytest.fixture(scope="session")
def available_tools() -> list[dict]:
    # run_shell_command is the DSTT handler's fallback — not offered to transition2exec
    return [t for t in build_catalog() if t["name"] != "run_shell_command"]


@pytest.fixture(scope="session", autouse=True)
def require_endpoint():
    if not _endpoint_available():
        pytest.skip("transition2exec endpoint not reachable at " + ENDPOINT)


def _assert_seed(seed: dict, available_tools: list[dict], not_mappable_ids: set[str]):
    """Shared assertion logic for baseline and stress seeds."""
    response = _call_transition2exec(seed, available_tools)
    status, actual_tool, actual_inputs = _parse_response(response)

    expected = seed["expected"]
    expected_tool = expected["tool"]
    expected_inputs = expected.get("inputs", {})

    if seed["id"] in not_mappable_ids:
        assert status == "not_mappable" or actual_tool == "not_mappable", (
            f"[{seed['id']}] expected not_mappable, got status={status!r} tool={actual_tool!r}\n"
            f"response: {response}"
        )
    else:
        assert status == "ok", (
            f"[{seed['id']}] expected status=ok, got {status!r}\nresponse: {response}"
        )
        assert actual_tool == expected_tool, (
            f"[{seed['id']}] wrong tool: got {actual_tool!r}, expected {expected_tool!r}"
        )
        assert actual_inputs == expected_inputs, (
            f"[{seed['id']}] wrong inputs:\n"
            f"  got:      {actual_inputs}\n"
            f"  expected: {expected_inputs}"
        )


# ---------------------------------------------------------------------------
# Baseline regression tests (17 seeds)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", _seeds, ids=_seed_ids)
def test_seed(seed: dict, available_tools: list[dict]):
    _assert_seed(seed, available_tools, NOT_MAPPABLE_IDS)


# ---------------------------------------------------------------------------
# Stress tests (20 seeds) — harder tool selection + input resolution edge cases
# ---------------------------------------------------------------------------

_stress_seeds = _load_stress_seeds()
_stress_seed_ids = [s["id"] for s in _stress_seeds]


@pytest.mark.stress
@pytest.mark.parametrize("seed", _stress_seeds, ids=_stress_seed_ids)
def test_seed_stress(seed: dict, available_tools: list[dict]):
    _assert_seed(seed, available_tools, STRESS_NOT_MAPPABLE_IDS)
