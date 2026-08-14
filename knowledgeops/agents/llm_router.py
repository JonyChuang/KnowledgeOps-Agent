from __future__ import annotations

import json

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from .state import AgentIntent


class RouteDecision(BaseModel):
    intent: AgentIntent
    ticket_id: str | None = None
    ticket_statuses: list[str] = Field(default_factory=list)


class OpenAIIntentRouter:
    def __init__(
        self,
        *,
        client: AsyncOpenAI,
        model: str,
        temperature: float = 0,
    ) -> None:
        self.client = client
        self.model = model
        self.temperature = temperature

    async def route(self, user_message: str) -> AgentIntent | None:
        message = user_message.strip()
        if not message:
            return None

        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是企业知识库 Agent 的意图分类器。"
                        "仅返回 JSON，不要 Markdown。"
                        'JSON 格式：{"intent":"general_chat|knowledge_qa|ticket_query|ticket_create",'
                        '"ticket_id":null,"ticket_statuses":[]}。'
                        "总结、解释、查询知识库、排查流程属于 knowledge_qa。"
                        "查询、查看、列出工单属于 ticket_query。"
                        "创建、新建、提交、报修工单属于 ticket_create。"
                        "问候、能力咨询、信息不足的闲聊属于 general_chat。"
                        "不确定时 intent 返回 general_chat。"
                    ),
                },
                {"role": "user", "content": message},
            ],
        )

        content = response.choices[0].message.content
        if not content:
            return None

        try:
            decision = RouteDecision.model_validate(json.loads(content))
        except (json.JSONDecodeError, ValueError):
            return None

        return decision.intent
