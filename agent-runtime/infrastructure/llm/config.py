from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()


def _get_env(*names: str, default: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


BASE_URL = _get_env("BASE_URL", "OPENAI_BASE_URL", "LOCAL_API_URL", default="http://127.0.0.1:11434/v1")
API_KEY = _get_env("API_KEY", "OPENAI_API_KEY", "LOCAL_API_KEY", default="ollama")
MODEL = _get_env("MODEL", "OPENAI_MODEL", "LLM_MODEL", default="llama3")
TEMPERATURE = float(_get_env("TEMPERATURE", default="0.7"))
MAX_TOKENS = int(_get_env("MAX_TOKENS", default="500"))

