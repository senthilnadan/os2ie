"""
OS2I TaskExecutor service — HTTP wrapper around the kernel.

POST /execute   { task, context } → ExecutionResult
GET  /health    → { status: ok }

Start:
    python -m src.server
or:
    uvicorn src.server:app --port 8009
"""
from __future__ import annotations
from typing import Any
from fastapi import FastAPI
from pydantic import BaseModel
from .catalog import build_catalog
from .clients import Task2PlanClient, Transition2ExecClient, Transition2ShellClient
from .config import config
from .kernel import execute


app = FastAPI(title="OS2I TaskExecutor", version="1.0.0")

_catalog = build_catalog()
_available_tools = [t for t in _catalog if t["name"] != "run_shell_command"]


class ExecuteRequest(BaseModel):
    task: str
    context: dict[str, Any] = {}
    strategy: str = "input_first"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/execute")
def execute_task(req: ExecuteRequest):
    t2p = Task2PlanClient(config.task2plan_url)
    t2e = Transition2ExecClient(config.transition2exec_url)
    t2s = Transition2ShellClient(config.transition2shell_url)

    abstract_dstt, meta = t2p.plan(req.task)

    result = execute(req.task, req.context, abstract_dstt, t2e,
                     available_tools=_available_tools, t2s=t2s, strategy=req.strategy)

    return result.model_dump()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server:app", host="0.0.0.0", port=8009, reload=False)
