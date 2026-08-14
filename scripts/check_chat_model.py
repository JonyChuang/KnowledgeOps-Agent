import asyncio

from openai import AsyncOpenAI

from knowledgeops.config import get_settings


async def main() -> None:
    settings = get_settings()

    if not settings.chat_model:
        raise RuntimeError("CHAT_MODEL is not configured.")

    if settings.chat_api_key is None:
        raise RuntimeError("CHAT_API_KEY is not configured.")

    client = AsyncOpenAI(
        api_key=settings.chat_api_key.get_secret_value(),
        base_url=settings.chat_base_url,
    )

    response = await client.chat.completions.create(
        model=settings.chat_model,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": "只回复：Chat 模型连接成功",
            }
        ],
    )

    print(response.choices[0].message.content)


if __name__ == "__main__":
    asyncio.run(main())