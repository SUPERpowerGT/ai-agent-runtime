from __future__ import annotations

from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parent


class _SafePromptContext(dict):
    def __missing__(self, key: str) -> str:
        return ""


def render_prompt(name: str, **context) -> str:
    """
    Load a prompt template from prompts/<name>.md and format it with context.
    """
    template_path = PROMPTS_DIR / f"{name}.md"
    template = template_path.read_text(encoding="utf-8")
    return template.format_map(_SafePromptContext(context)).strip()
