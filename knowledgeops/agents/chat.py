from __future__ import annotations

from typing import Protocol

from openai import AsyncOpenAI

from .state import AgentCitation, AgentConversationMessage


class ChatAnswerGenerator(Protocol):
    async def answer_general_chat(
        self,
        user_message: str,
        conversation_history: list[AgentConversationMessage],
    ) -> str:
        ...

    async def answer_from_citations(
        self,
        question: str,
        citations: list[AgentCitation],
    ) -> str:
        ...


class UnavailableChatAnswerGenerator:
    """Give an actionable response when a Chat model is not configured."""

    async def answer_general_chat(
        self,
        user_message: str,
        conversation_history: list[AgentConversationMessage],
    ) -> str:
        return (
            "当前智能助手尚未配置 Chat 模型，暂时不能进行自由对话。"
            "请由管理员检查 CHAT_MODEL、CHAT_BASE_URL 和 CHAT_API_KEY。"
        )

    async def answer_from_citations(
        self,
        question: str,
        citations: list[AgentCitation],
    ) -> str:
        raise RuntimeError(
            "知识库问答需要先配置 CHAT_MODEL、CHAT_BASE_URL 和 CHAT_API_KEY。"
        )


class OpenAIChatAnswerGenerator:
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

    async def answer_general_chat(
        self,
        user_message: str,
        conversation_history: list[AgentConversationMessage],
    ) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是 KnowledgeOps 企业知识与工单协同助手。使用自然、简洁的中文进行多轮对话，"
                    "可以解释功能、协助梳理问题和给出下一步建议。不要编造企业内部制度、工单状态、"
                    "知识库内容或操作结果；涉及这些信息时，应提示用户通过相应的知识库或工单工具查询。"
                    "创建或修改工单必须由工作流显式确认，不能在普通对话中声称已经完成。"
                ),
            },
            *[
                {"role": message.role, "content": message.content}
                for message in conversation_history[-8:]
            ],
            {"role": "user", "content": user_message},
        ]
        return await self._complete(messages)

    async def answer_from_citations(
        self,
        question: str,
        citations: list[AgentCitation],
    ) -> str:
        sources = "\n\n".join(
            f"[来源 {index + 1}: {citation.source_name}]\n{citation.text}"
            for index, citation in enumerate(citations)
        )

        return await self._complete(
            [
                {
                    "role": "system",
                    "content": (
                        "你是企业知识库助手。只能依据提供的来源回答。"
                        "若来源不能回答，明确说明“知识库中没有足够信息”。"
                        "不要编造事实、流程或来源。使用中文，回答简洁。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"问题：{question}\n\n可用来源：\n{sources}",
                },
            ]
        )

    async def _complete(self, messages: list[dict[str, str]]) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=messages,
        )
        content = response.choices[0].message.content
        if not content or not content.strip():
            raise RuntimeError("Chat model returned an empty answer.")

        return content.strip()
