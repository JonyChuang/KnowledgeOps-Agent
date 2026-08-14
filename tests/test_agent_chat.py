from types import SimpleNamespace

import pytest

from knowledgeops.agents.chat import OpenAIChatAnswerGenerator
from knowledgeops.agents.state import AgentCitation, AgentConversationMessage


class FakeCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


def make_generator(content: str = "收到，我会继续协助你。"):
    completions = FakeCompletions(content)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return (
        OpenAIChatAnswerGenerator(client=client, model="chat-test", temperature=0.2),
        completions,
    )


@pytest.mark.asyncio
async def test_chat_generator_sends_history_to_standard_chat_completion() -> None:
    generator, completions = make_generator()
    history = [
        AgentConversationMessage(role="user", content="我在排查 VPN。"),
        AgentConversationMessage(role="assistant", content="请描述错误信息。"),
    ]

    answer = await generator.answer_general_chat("错误代码是 619。", history)

    assert answer == "收到，我会继续协助你。"
    assert len(completions.calls) == 1
    request = completions.calls[0]
    assert request["model"] == "chat-test"
    assert request["temperature"] == 0.2
    assert "多轮对话" in request["messages"][0]["content"]
    assert request["messages"][1:] == [
        {"role": "user", "content": "我在排查 VPN。"},
        {"role": "assistant", "content": "请描述错误信息。"},
        {"role": "user", "content": "错误代码是 619。"},
    ]


@pytest.mark.asyncio
async def test_chat_generator_keeps_knowledge_answers_grounded_in_citations() -> None:
    generator, completions = make_generator("请检查企业账号状态。")
    citation = AgentCitation(
        chunk_id="chunk-1",
        document_id="document-1",
        source_name="vpn-guide.md",
        source_type="markdown",
        chunk_index=0,
        start_char=0,
        end_char=20,
        text="VPN 连接需要使用企业账号。",
        score=0.9,
        sources=["vector"],
    )

    answer = await generator.answer_from_citations("VPN 为什么连不上？", [citation])

    assert answer == "请检查企业账号状态。"
    request = completions.calls[0]
    assert request["model"] == "chat-test"
    assert request["temperature"] == 0.2
    assert "只能依据提供的来源回答" in request["messages"][0]["content"]
    assert "vpn-guide.md" in request["messages"][1]["content"]
