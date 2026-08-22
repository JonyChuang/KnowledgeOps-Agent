"""Generate v0.4 hard-retrieval and grounded-answer evaluation assets."""

from __future__ import annotations

import json
from pathlib import Path

from generate_evaluation_v02 import DOCUMENTS

ROOT = Path(__file__).parents[1]
FIXTURE_DIR = ROOT / "docs" / "evaluation" / "fixtures-v0.4"
DATASET_PATH = ROOT / "docs" / "evaluation" / "knowledgeops-gold-v0.4.json"
PLACEHOLDER_KNOWLEDGE_BASE_ID = "replace-with-a-real-knowledge-base-id"

EXTRA_DOCUMENTS = (
    ("endpoint-patching", "Endpoint patching", "security", "Endpoint security updates need staged deployment", "A laptop has missed its security updates", "Validate device health and deploy the approved patch ring", "Record device, patch ring, and completion time", "Handle patch compliance rather than hardware replacement", "Critical patches must start within four hours"),
    ("mobile-management", "Mobile device management", "security", "A managed phone needs enrollment or policy repair", "My work phone cannot apply the company profile", "Verify ownership and re-enroll the managed profile", "Record device identifier and profile status", "Handle mobile management rather than password reset", "Enrollment issues are reviewed within one business day"),
    ("mail-quarantine", "Mail quarantine", "collaboration", "A legitimate business email is quarantined", "A supplier email did not reach my inbox", "Validate sender reputation and release only after review", "Record sender domain and message identifier", "Handle quarantine review rather than mailbox storage", "High-priority releases are reviewed within two hours"),
    ("data-retention", "Data retention", "governance", "Business records need a documented retention period", "How long should this project record be kept", "Classify the record before applying the retention schedule", "Record classification, owner, and retention date", "Handle retention policy rather than backup recovery", "Retention labels are applied before publication"),
    ("vendor-access", "Vendor access", "access", "An external vendor requests time-bounded access", "A supplier needs temporary access to a portal", "Confirm contract owner and least-privilege scope", "Record sponsor, expiry, and approved systems", "Handle vendor access rather than employee onboarding", "Access expires after the approved engagement window"),
    ("remote-desktop", "Remote desktop support", "support", "An employee needs a secure remote support session", "Support needs to view my laptop", "Start an approved session after employee consent", "Record session owner, time, and consent", "Handle remote support rather than privileged administration", "Sessions require consent before connection"),
    ("certificate-renewal", "Certificate renewal", "platform", "A service certificate approaches expiration", "Our internal site certificate expires soon", "Verify service owner and renew through the certificate process", "Record certificate name, owner, and expiry", "Handle certificate renewal rather than DNS troubleshooting", "Renewal starts thirty days before expiry"),
    ("backup-restore", "Backup restore", "platform", "A business owner requests restoration of protected data", "Can we recover last week's file version", "Confirm restore point and business owner approval", "Record source, restore target, and approval", "Handle restore requests rather than retention deletion", "Urgent restores are acknowledged within one hour"),
    ("software-license", "Software license assignment", "assets", "An employee needs a licensed application", "I need access to the design software", "Verify entitlement and assign an available license", "Record product, requester, and license pool", "Handle licensing rather than privileged access", "Standard assignments complete within one business day"),
    ("expense-system", "Expense system access", "finance", "An employee cannot submit an expense report", "The expense portal rejects my submission", "Verify employee profile and cost-center mapping", "Record report identifier and error message", "Handle expense access rather than payroll correction", "Finance access issues receive an initial response in four hours"),
    ("payroll-correction", "Payroll correction", "finance", "An employee reports an incorrect payroll amount", "My latest salary payment looks wrong", "Verify payroll period and route the correction to payroll operations", "Record period, discrepancy, and employee confirmation", "Handle payroll correction rather than expense approval", "Payroll discrepancies are acknowledged within one business day"),
    ("onboarding", "Employee onboarding", "people", "A new employee needs standard first-day access", "A new joiner cannot access required tools", "Validate start date and approved role template", "Record employee, manager, and assigned package", "Handle onboarding rather than external vendor access", "Standard access is ready on the start date"),
    ("offboarding", "Employee offboarding", "people", "A departing employee's access must be removed", "A contractor leaves tomorrow", "Validate departure notice and revoke assigned access", "Record departure time and revoked systems", "Handle offboarding rather than leave management", "High-risk access is removed by the departure time"),
    ("identity-proofing", "Identity proofing", "identity", "A sensitive request needs identity verification", "I changed phones and need account recovery", "Verify identity through approved recovery factors", "Record verification method and reviewer", "Handle proofing rather than ordinary password reset", "High-risk recovery requires same-day review"),
    ("analytics-access", "Analytics workspace access", "data", "An analyst requests access to a governed dataset", "I need the sales dashboard dataset", "Verify data owner approval and role scope", "Record dataset, purpose, and expiry", "Handle analytics access rather than file sharing", "Access requests are reviewed within one business day"),
    ("release-change", "Production change request", "engineering", "A team plans a controlled production change", "We need to deploy a service configuration", "Verify change owner, rollback plan, and approval", "Record change window, risk, and rollback owner", "Handle controlled change rather than incident escalation", "High-risk changes require approval before the change window"),
)

TOPICS = (*DOCUMENTS, *EXTRA_DOCUMENTS)
VARIANTS = (
    ("policy", "Policy", "APPROVAL_SCOPE=service_owner", "POLICY_ACTION=record business justification"),
    ("procedure", "Procedure", "STANDARD_ACTION=follow approved runbook", "PROCEDURE_RECORD=record owner and completion time"),
    ("exception", "Exception", "EXCEPTION_TRIGGER=high impact incident", "EXCEPTION_ACTION=escalate to service desk"),
    ("archive", "Archived", "ARCHIVED_STATUS=do not use", "ARCHIVED_ACTION=use the current policy instead"),
)
QUESTION_STYLES = ("direct", "paraphrase", "boundary", "version", "process")


def fixture_markdown(topic: tuple[str, str, str, str, str, str, str, str, str], variant: tuple[str, str, str, str]) -> str:
    slug, title, domain, scenario, paraphrase, action, record, contrast, deadline = topic
    _variant_slug, variant_title, control, requirement = variant
    return "\n".join(
        (
            f"# {title}: {variant_title}",
            "",
            f"TOPIC={slug}",
            f"DOMAIN={domain}",
            f"SCENARIO={scenario}",
            f"EMPLOYEE_DESCRIPTION={paraphrase}",
            f"CURRENT_ACTION={action}",
            f"RECORD_REQUIREMENT={record}",
            f"BOUNDARY={contrast}",
            f"TIMELINE={deadline}",
            control,
            requirement,
            "This is a fictional, desensitized v0.4 evaluation document.",
        )
    )


def retrieval_cases() -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for topic in TOPICS:
        slug, title, _domain, _scenario, paraphrase, _action, _record, contrast, _deadline = topic
        for variant_slug, variant_title, control, requirement in VARIANTS:
            source_name = f"{slug}-{variant_slug}.md"
            questions = (
                f"What is the current {variant_title} for {title}? {control}",
                f"An employee says '{paraphrase}'. Which {title} {variant_title} document applies?",
                f"For {title}, distinguish {variant_title} from this boundary: {contrast}",
                f"Is the {title} document with {control} current or archived?",
                f"When handling {title}, which document requires: {requirement}?",
            )
            for style, query in zip(QUESTION_STYLES, questions, strict=True):
                cases.append(
                    {
                        "id": f"retrieval-{slug}-{variant_slug}-{style}",
                        "query": query,
                        "knowledge_base_id": PLACEHOLDER_KNOWLEDGE_BASE_ID,
                        "identifier": "source_name",
                        "relevant_ids": [source_name],
                        "category": f"hard_{style}",
                    }
                )
    return cases


def multi_hop_cases() -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for slug, title, *_ in TOPICS:
        pairs = (
            ("policy", "procedure", "APPROVAL_SCOPE=service_owner", "STANDARD_ACTION=follow approved runbook"),
            ("procedure", "exception", "PROCEDURE_RECORD=record owner and completion time", "EXCEPTION_ACTION=escalate to service desk"),
            ("policy", "exception", "POLICY_ACTION=record business justification", "EXCEPTION_TRIGGER=high impact incident"),
        )
        for index, (first, second, first_fact, second_fact) in enumerate(pairs, start=1):
            cases.append(
                {
                    "id": f"multihop-{slug}-{index}",
                    "question": f"For {title}, combine the current {first} and {second}: what controls and actions apply?",
                    "knowledge_base_id": PLACEHOLDER_KNOWLEDGE_BASE_ID,
                    "required_source_names": [f"{slug}-{first}.md", f"{slug}-{second}.md"],
                    "required_facts": [first_fact, second_fact],
                    "category": "two_document_answer",
                }
            )
        cases.append(
            {
                "id": f"multihop-{slug}-abstain",
                "question": f"What is the cafeteria meal subsidy for the {title} team?",
                "knowledge_base_id": PLACEHOLDER_KNOWLEDGE_BASE_ID,
                "required_source_names": [],
                "required_facts": [],
                "should_abstain": True,
                "category": "unanswerable",
            }
        )
    return cases


def agent_cases() -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for index in range(20):
        cases.append({"id": f"agent-general-{index + 1}", "user_message": f"你好，这是第 {index + 1} 个普通咨询。", "expected_tool_names": [], "expected_behavior": "direct", "category": "general_chat"})
    for index, topic in enumerate(TOPICS[:20], start=1):
        cases.append({"id": f"agent-search-{index}", "user_message": f"{topic[1]} 遇到问题时应该查什么规则？", "expected_tool_names": ["search_knowledge_base"], "category": "knowledge_qa"})
    for index in range(15):
        cases.append({"id": f"agent-list-{index + 1}", "user_message": "请查看我的工单列表。", "expected_tool_names": ["list_my_tickets"], "category": "ticket_query"})
    for index in range(10):
        cases.append({"id": f"agent-detail-{index + 1}", "user_message": f"查看工单 TKT-V04-{index + 1:03d} 的详情。", "expected_tool_names": ["get_my_ticket_detail"], "category": "ticket_query"})
    for index, topic in enumerate(TOPICS[:15], start=1):
        cases.append({"id": f"agent-clarify-{index}", "user_message": f"{topic[1]} 影响我的工作，请帮我创建支持工单。", "expected_tool_names": [], "expected_behavior": "clarify", "required_response_keywords": ["补充"], "category": "ticket_create_clarify"})
    for index, topic in enumerate(TOPICS[:15], start=1):
        cases.append({"id": f"agent-followup-draft-{index}", "user_message": "问题持续三十分钟，只影响我本人，优先级为 medium，请生成工单草稿。", "conversation_history": [{"role": "user", "content": f"{topic[1]} 影响我的工作，请帮我创建支持工单。"}, {"role": "assistant", "content": "请补充影响范围、优先级和持续时间。"}], "expected_tool_names": ["prepare_ticket_draft"], "requires_confirmation": True, "category": "ticket_create_followup"})
    for index, topic in enumerate(TOPICS[15:20], start=16):
        cases.append({"id": f"agent-complete-draft-{index}", "user_message": f"{topic[1]} 已持续三十分钟，只影响我本人，优先级为 medium，请生成支持工单草稿。", "expected_tool_names": ["prepare_ticket_draft"], "requires_confirmation": True, "category": "ticket_create_complete"})
    return cases


def security_cases() -> list[dict[str, str]]:
    controls = (
        ("unconfirmed-create", "No ticket is written before employee confirmation"),
        ("double-confirm", "Repeated confirmation cannot create a second ticket"),
        ("cross-employee-read", "An employee cannot read another employee's ticket"),
        ("cross-employee-conversation", "An employee cannot resume another employee's Agent confirmation"),
        ("service-desk-role", "A requester cannot call service-desk transition APIs"),
        ("unassigned-claim", "Only service-desk operators can claim unassigned tickets"),
        ("assignee-transition", "A non-assignee cannot alter an active ticket"),
        ("web-loopback", "Web import rejects loopback destinations"),
        ("web-private-ip", "Web import rejects private-network destinations"),
        ("web-credential-url", "Web import rejects credential-bearing URLs"),
        ("invalid-ticket", "Unknown ticket IDs do not disclose protected data"),
        ("invalid-conversation", "Unknown conversation IDs do not disclose protected data"),
        ("ticket-audit", "Ticket workflow retains activity events"),
        ("confirmation-cancel", "Cancelled drafts create no ticket"),
        ("employee-scope", "Ticket listing is scoped to the current employee"),
        ("upload-type", "Unsupported local file types are rejected"),
    )
    return [
        {"id": f"security-{suffix}-{index}", "scenario": scenario, "expected_outcome": "API integration test passes"}
        for index in range(1, 3)
        for suffix, scenario in controls
    ]


def main() -> None:
    if len(TOPICS) != 40:
        raise RuntimeError("v0.4 requires exactly 40 topics.")
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for topic in TOPICS:
        for variant in VARIANTS:
            (FIXTURE_DIR / f"{topic[0]}-{variant[0]}.md").write_text(
                fixture_markdown(topic, variant), encoding="utf-8"
            )
    dataset = {
        "schema_version": "knowledgeops-evaluation/v1",
        "dataset_version": "v0.4",
        "name": "KnowledgeOps hard retrieval and grounded-answer gold set",
        "retrieval_cases": retrieval_cases(),
        "agent_cases": agent_cases(),
        "multi_hop_cases": multi_hop_cases(),
        "security_cases": security_cases(),
    }
    DATASET_PATH.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(TOPICS) * len(VARIANTS)} fixtures to {FIXTURE_DIR}")
    print(f"Wrote {len(dataset['retrieval_cases'])} retrieval cases to {DATASET_PATH}")


if __name__ == "__main__":
    main()
