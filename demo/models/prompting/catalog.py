from __future__ import annotations
from typing import Callable
from .tools import ChainOfThought, VerifyAndCorrect, DecomposeThenExecute, CriticRefineLoop

# Tool specs — fed to transition2exec as available_tools
CATALOG = [
    {
        "name": "chain_of_thought",
        "description": "Reason step by step before answering a question",
        "inputs": ["question"],
        "outputs": ["answer"],
    },
    {
        "name": "verify_and_correct",
        "description": "Verify a statement for accuracy and return a corrected version",
        "inputs": ["statement"],
        "outputs": ["verified"],
    },
    {
        "name": "decompose_then_execute",
        "description": "Break a complex task into steps, then execute each step",
        "inputs": ["task"],
        "outputs": ["result"],
    },
    {
        "name": "critic_refine",
        "description": "Critique a draft and produce a refined, improved version",
        "inputs": ["draft"],
        "outputs": ["refined"],
    },
]


def build_tool_provider(model) -> dict:
    """Runtime tool_provider for the kernel.

    Args:
        model: str → OllamaProvider shorthand, or any callable (str) -> str
    """
    from demo.lib.prompting import OllamaProvider
    provider = OllamaProvider(model) if isinstance(model, str) else model
    return {
        "chain_of_thought": ChainOfThought(provider),
        "verify_and_correct": VerifyAndCorrect(provider),
        "decompose_then_execute": DecomposeThenExecute(provider),
        "critic_refine": CriticRefineLoop(provider),
    }
