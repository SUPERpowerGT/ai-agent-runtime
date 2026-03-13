from openai import OpenAI
from infra import config

client = OpenAI(
    api_key=config.API_KEY,
    base_url=config.BASE_URL
)


def call_llm(prompt: str):

    response = client.chat.completions.create(
        model=config.MODEL,
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=config.TEMPERATURE,
        max_tokens=config.MAX_TOKENS
    )

    print(response)

    return response.choices[0].message.content