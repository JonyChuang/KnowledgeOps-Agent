"""Deterministic completeness checks for employee ticket intake."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

_CREATE_TICKET_PATTERN = re.compile(
    r"(?:"
    r"(?:创建|新建|提交|生成|开|提).{0,16}(?:工单|报修|服务请求)"
    r"|(?:工单|报修|服务请求).{0,16}(?:创建|新建|提交|生成|开|提)"
    r"|\b(?:create|open|submit|file|raise|log|draft)\b.{0,40}"
    r"\b(?:ticket|support\s+(?:ticket|case)|service\s+request)\b"
    r")",
    re.IGNORECASE,
)
_HOW_TO_PATTERN = re.compile(
    r"(?:如何|怎么|怎样|是否|能否|how\s+to|can\s+i)"
    r".{0,24}(?:创建|新建|提交|生成|工单|报修|ticket)",
    re.IGNORECASE,
)
_REQUEST_NOISE_PATTERN = re.compile(
    r"(?:"
    r"请|帮我|麻烦|一个|创建|新建|提交|生成|开|提|工单|报修|服务请求|支持"
    r"|please|help|me|create|open|submit|file|raise|log|draft|ticket|support"
    r"|影响.{0,4}(?:工作|业务)|影响我本人|只影响我本人|impact.{0,12}(?:work|business)"
    r")",
    re.IGNORECASE,
)
_CONTEXT_PATTERN = re.compile(
    r"(?:"
    r"(?:\d+|[一二三四五六七八九十]+)(?:分钟|小时|天|分|秒)"
    r"|\b\d{1,2}:\d{2}\b"
    r"|(?:今天|昨天|上午|下午|晚上|刚才|之后|开始于|持续|报错|错误码|错误信息|提示"
    r"|重启|尝试|复现|步骤|版本|客户端|浏览器|设备|笔记本|手机|电脑|系统|办公室|远程)"
    r"|\b(?:error|code|message|windows|mac(?:os)?|ios|android|browser|client|"
    r"device|laptop|desktop|mobile|version|after|when|while|since|today|"
    r"yesterday|morning|afternoon|restarted|tried|step|office|home|remote|wifi)\b"
    r")",
    re.IGNORECASE,
)
_IMPACT_PATTERN = re.compile(
    r"(?:"
    r"影响|无法|不能|阻塞|中断|受影响|只影响|本人|团队|部门|公司|全员|业务"
    r"|\b(?:impact|affect(?:ed|ing)?|unable|cannot|can't|block(?:ed|ing)?|"
    r"prevent(?:ed|ing)?|interrupt(?:ed|ing)?|single\s+user|team|department|company)\b"
    r")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TicketIntakeAssessment:
    """The service-side view of whether an employee report is actionable."""

    is_ticket_request: bool
    missing_fields: tuple[str, ...] = ()

    @property
    def requires_clarification(self) -> bool:
        return self.is_ticket_request and bool(self.missing_fields)

    @property
    def clarification_message(self) -> str:
        if not self.requires_clarification:
            return ""
        missing = "、".join(self.missing_fields)
        return (
            "为了让服务台能够准确处理，并避免根据猜测创建工单，请补充："
            f"{missing}。可提供报错信息、发生时间、使用的设备或系统、已尝试操作，"
            "以及受影响的人员或业务范围；收到后我会生成待确认的工单草稿。"
        )


def assess_ticket_intake(user_messages: Iterable[str]) -> TicketIntakeAssessment:
    """Check only employee-supplied facts before a ticket draft can be prepared.

    A ticket needs a concrete issue, operational context, and a stated business
    impact. The rule deliberately accepts several common forms of context rather
    than relying on a category-specific vocabulary, so it remains useful for new
    IT, facilities, HR, and business-service request types.
    """
    messages = [message.strip() for message in user_messages if message.strip()]
    if not messages:
        return TicketIntakeAssessment(is_ticket_request=False)

    text = "\n".join(messages)
    if _HOW_TO_PATTERN.search(messages[-1]) or not _CREATE_TICKET_PATTERN.search(text):
        return TicketIntakeAssessment(is_ticket_request=False)

    missing_fields: list[str] = []
    if not _has_concrete_issue(text):
        missing_fields.append("具体问题现象")
    if not _CONTEXT_PATTERN.search(text):
        missing_fields.append("发生场景或已尝试操作")
    if not _IMPACT_PATTERN.search(text):
        missing_fields.append("受影响范围或业务影响")
    return TicketIntakeAssessment(
        is_ticket_request=True,
        missing_fields=tuple(missing_fields),
    )


def _has_concrete_issue(text: str) -> bool:
    remainder = _REQUEST_NOISE_PATTERN.sub(" ", text)
    return bool(re.search(r"[A-Za-z0-9]{2,}|[\u4e00-\u9fff]{2,}", remainder))
