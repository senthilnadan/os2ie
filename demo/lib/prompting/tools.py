from __future__ import annotations
import json
import requests
from typing import Callable, Union


class AskTool:
    """Send a raw prompt to the model. Input: prompt (str)."""

    def __init__(self, provider: Callable[[str], str]) -> None:
        self._provider = provider

    def execute(self, prompt: str) -> str:
        return self._provider(prompt)


class AskTemplateTool:
    """Fill {{0}}, {{1}}, ... placeholders in a template, then send to model.

    Inputs: template (str), *values
    """

    def __init__(self, provider: Callable[[str], str]) -> None:
        self._provider = provider

    def execute(self, template: str, *values) -> str:
        prompt = template
        for i, val in enumerate(values):
            prompt = prompt.replace(f"{{{{{i}}}}}", str(val))
        return self._provider(prompt)


class AskStructuredTool:
    """Send a prompt to the model and return structured output.

    schema: str  → appended as a plain instruction; returns raw str
    schema: dict → appended as a JSON field instruction; returns validated dict

    validate (dict schema only): if True, all declared keys must be present in the
    response. If False, the parsed dict is returned as-is — missing keys propagate
    to the caller.

    Retries once on connection error only. Validation failures raise immediately.
    """

    def __init__(
        self,
        provider: Callable[[str], str],
        schema: Union[str, dict[str, str]],
        validate: bool = True,
        max_retries: int = 1,
    ) -> None:
        self._provider = provider
        self._schema = schema
        self._validate = validate
        self._max_retries = max_retries

    def execute(self, prompt: str) -> Union[str, dict]:
        full_prompt = self._build_prompt(prompt)
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = self._provider(full_prompt)
                break
            except requests.RequestException as exc:
                last_exc = exc
                if attempt == self._max_retries:
                    raise
        else:
            raise last_exc  # type: ignore[misc]

        if isinstance(self._schema, str):
            return response

        return self._parse_and_validate(response)

    def _build_prompt(self, prompt: str) -> str:
        if isinstance(self._schema, str):
            return f"{prompt}\n\n{self._schema}"

        field_lines = "\n".join(
            f'  "{k}": {v}' for k, v in self._schema.items()
        )
        instruction = (
            "---\n"
            "Respond with a JSON object and nothing else. Use exactly these keys:\n"
            f"{field_lines}\n\n"
            "Output only the JSON object. No explanation, no markdown fences."
        )
        return f"{prompt}\n\n{instruction}"

    def _parse_and_validate(self, response: str) -> dict:
        cleaned = response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Model response is not valid JSON: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError(f"Expected a JSON object, got {type(data).__name__}")

        if self._validate:
            missing = [k for k in self._schema if k not in data]
            if missing:
                raise ValueError(f"Response missing required keys: {missing}")

        return {k: data[k] for k in self._schema if k in data} if self._validate else data


class AskStructuredMultiTool:
    """Like AskStructuredTool but returns schema field values as an ordered list.

    Enables multi-output transitions — the kernel maps each value to its
    corresponding output key via the existing list-unpacking path:
      outputs: ["thought", "initial_values_json", "transitions_json"]
      → execute() returns [thought_val, iv_val, tr_val]

    Schema key order = output key order in the DSTT transition.
    Retry and validation behaviour identical to AskStructuredTool.
    """

    def __init__(
        self,
        provider: Callable[[str], str],
        schema: dict[str, str],
        validate: bool = True,
        max_retries: int = 1,
    ) -> None:
        self._inner = AskStructuredTool(provider, schema, validate, max_retries)
        self._schema = schema

    def execute(self, prompt: str) -> list:
        data = self._inner.execute(prompt)
        result = []
        for k in self._schema:
            val = data.get(k, "")
            # Serialize dicts/lists to JSON strings so downstream state keys are strings
            if not isinstance(val, str):
                val = json.dumps(val)
            result.append(val)
        return result


def build_tool_provider(
    model,
    structured_schemas: dict[str, Union[str, dict[str, str]]] | None = None,
) -> dict:
    """Build tool_provider from a model name string or any callable provider.

    Args:
        model: str → OllamaProvider shorthand, or any callable (str) -> str
        structured_schemas: optional dict of tool_name → schema for AskStructuredTool
            e.g. {"classify": {"label": "category name", "score": "0.0–1.0"}}
    """
    from .providers import OllamaProvider
    provider = OllamaProvider(model) if isinstance(model, str) else model
    tools: dict = {
        "ask": AskTool(provider),
        "asktemplate": AskTemplateTool(provider),
    }
    if structured_schemas:
        for name, schema in structured_schemas.items():
            tools[name] = AskStructuredTool(provider, schema)
    return tools
