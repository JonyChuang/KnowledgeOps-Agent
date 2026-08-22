from knowledgeops.agents.ticket_intake import assess_ticket_intake


def test_incomplete_ticket_request_requires_operational_context() -> None:
    assessment = assess_ticket_intake(
        ["VPN connection failure 影响我的工作，请帮我创建支持工单。"]
    )

    assert assessment.is_ticket_request is True
    assert assessment.missing_fields == ("发生场景或已尝试操作",)
    assert "补充" in assessment.clarification_message


def test_complete_ticket_request_can_continue_to_draft() -> None:
    assessment = assess_ticket_intake(
        [
            (
                "VPN 在 Windows 11 客户端报错 619，重启后仍然失败，"
                "已持续三十分钟，只影响我的远程办公，请创建支持工单草稿。"
            )
        ]
    )

    assert assessment.is_ticket_request is True
    assert assessment.requires_clarification is False


def test_follow_up_employee_message_completes_the_original_ticket_report() -> None:
    assessment = assess_ticket_intake(
        [
            "VPN connection failure 影响我的工作，请帮我创建支持工单。",
            "问题持续三十分钟，只影响我本人，优先级为 medium，请生成工单草稿。",
        ]
    )

    assert assessment.is_ticket_request is True
    assert assessment.requires_clarification is False


def test_how_to_create_ticket_is_not_treated_as_a_ticket_request() -> None:
    assessment = assess_ticket_intake(["如何创建支持工单？"])

    assert assessment.is_ticket_request is False
    assert assessment.requires_clarification is False
