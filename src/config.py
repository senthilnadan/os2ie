from __future__ import annotations
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Service URLs
    task2plan_url: str = "http://localhost:8000"
    transition2exec_url: str = "http://localhost:8002"

    # Default working directory for tool execution (run_shell_command, file ops)
    working_directory: Path = Path.cwd()


config = Config()
