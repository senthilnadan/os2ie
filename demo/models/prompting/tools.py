from __future__ import annotations
from typing import Callable
from demo.engine.kernel import DsttKernel
from demo.lib.prompting import build_tool_provider


class ChainOfThought:
    """Reason step by step before answering. Input: question (str)."""

    _dstt = {
        "segments": [{
            "transitions": [
                {"tool": "asktemplate", "inputs": ["_t_steps", "question"], "outputs": ["reasoning"]},
                {"tool": "asktemplate", "inputs": ["_t_answer", "reasoning"], "outputs": ["answer"]},
            ],
            "milestone": ["answer"],
        }]
    }
    _templates = {
        "_t_steps": "Think step by step to answer the following question.\nQuestion: {{0}}\nReasoning:",
        "_t_answer": "Based on this reasoning:\n{{0}}\n\nProvide a concise final answer.",
    }

    def __init__(self, provider: Callable[[str], str]) -> None:
        self._provider = provider

    def execute(self, question: str) -> str:
        state = {"question": question, **self._templates}
        result = DsttKernel().execute(self._dstt, build_tool_provider(self._provider), state)
        return result.state.get("answer", "")


class VerifyAndCorrect:
    """Verify a statement and correct it if wrong. Input: statement (str)."""

    _dstt = {
        "segments": [{
            "transitions": [
                {"tool": "asktemplate", "inputs": ["_t_verify", "statement"], "outputs": ["verdict"]},
                {"tool": "asktemplate", "inputs": ["_t_correct", "statement", "verdict"], "outputs": ["verified"]},
            ],
            "milestone": ["verified"],
        }]
    }
    _templates = {
        "_t_verify": "Is the following statement true or false? Explain briefly.\nStatement: {{0}}",
        "_t_correct": "Original statement: {{0}}\nVerification: {{1}}\n\nProvide the corrected, accurate statement.",
    }

    def __init__(self, provider: Callable[[str], str]) -> None:
        self._provider = provider

    def execute(self, statement: str) -> str:
        state = {"statement": statement, **self._templates}
        result = DsttKernel().execute(self._dstt, build_tool_provider(self._provider), state)
        return result.state.get("verified", "")


class DecomposeThenExecute:
    """Break a complex task into steps, then execute each step. Input: task (str)."""

    _dstt = {
        "segments": [{
            "transitions": [
                {"tool": "asktemplate", "inputs": ["_t_decompose", "task"], "outputs": ["steps"]},
                {"tool": "asktemplate", "inputs": ["_t_execute", "steps"], "outputs": ["result"]},
            ],
            "milestone": ["result"],
        }]
    }
    _templates = {
        "_t_decompose": "Break the following task into clear, numbered steps.\nTask: {{0}}",
        "_t_execute": "Execute each of the following steps and summarize the outcome.\nSteps:\n{{0}}",
    }

    def __init__(self, provider: Callable[[str], str]) -> None:
        self._provider = provider

    def execute(self, task: str) -> str:
        state = {"task": task, **self._templates}
        result = DsttKernel().execute(self._dstt, build_tool_provider(self._provider), state)
        return result.state.get("result", "")


class CriticRefineLoop:
    """Critique a draft and produce a refined version. Input: draft (str)."""

    _dstt = {
        "segments": [{
            "transitions": [
                {"tool": "asktemplate", "inputs": ["_t_critic", "draft"], "outputs": ["critique"]},
                {"tool": "asktemplate", "inputs": ["_t_refine", "draft", "critique"], "outputs": ["refined"]},
            ],
            "milestone": ["refined"],
        }]
    }
    _templates = {
        "_t_critic": "Critique the following draft. Identify weaknesses and suggest improvements.\nDraft: {{0}}",
        "_t_refine": "Original draft: {{0}}\nCritique: {{1}}\n\nRewrite the draft addressing all critique points.",
    }

    def __init__(self, provider: Callable[[str], str]) -> None:
        self._provider = provider

    def execute(self, draft: str) -> str:
        state = {"draft": draft, **self._templates}
        result = DsttKernel().execute(self._dstt, build_tool_provider(self._provider), state)
        return result.state.get("refined", "")
