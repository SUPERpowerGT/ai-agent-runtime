import time

from openai import OpenAI
from infra import config
from runtime.services.logging import log_llm

client = OpenAI(
    api_key=config.API_KEY,
    base_url=config.BASE_URL
)


def call_llm(prompt: str, state=None, agent_name: str | None = None):
    started_at = time.perf_counter()

    response = client.chat.completions.create(
        model=config.MODEL,
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=config.TEMPERATURE,
        max_tokens=config.MAX_TOKENS
    )

    duration_ms = (time.perf_counter() - started_at) * 1000

    if state is not None and hasattr(state, "record_llm_call"):
        state.record_llm_call(agent_name=agent_name, duration_ms=duration_ms)

    content = response.choices[0].message.content or ""
    log_llm(agent_name or "unknown", duration_ms, content)

    return content
