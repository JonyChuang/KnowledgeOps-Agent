"""Optional independent-model audit for grounded answer evaluation."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from openai import AsyncOpenAI

from .answers import MultiHopCaseResult
from .datasets import MultiHopGoldCase


class AnswerVerifier(Protocol):
    async def verify(
        self,
        *,
        question: str,
        required_facts: tuple[str, ...],
        should_abstain: bool,
        answer: str,
    ) -> bool:
        """Return whether the answer satisfies the supplied gold rubric."""


class OpenAIAnswerVerifier:
    """Ask a separately configured OpenAI-compatible model for a binary audit."""

    def __init__(self, *, client: AsyncOpenAI, model: str, temperature: float = 0) -> None:
        self.client = client
        self.model = model
        self.temperature = temperature

    async def verify(
        self,
        *,
        question: str,
        required_facts: tuple[str, ...],
        should_abstain: bool,
        answer: str,
    ) -> bool:
        rubric = (
            "The answer must explicitly state that available knowledge is insufficient."
            if should_abstain
            else "The answer must cover every required fact without contradiction: "
            + " | ".join(required_facts)
        )
        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an independent enterprise-answer verifier. "
                        "Judge the answer only against the supplied rubric. "
                        "Return exactly JSON: {\"pass\": true} or {\"pass\": false}."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Question: {question}\nRubric: {rubric}\nAnswer: {answer}",
                },
            ],
        )
        content = response.choices[0].message.content or ""
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as error:
            raise ValueError("Verifier did not return JSON.") from error
        if not isinstance(parsed, dict) or not isinstance(parsed.get("pass"), bool):
            raise TypeError("Verifier response must contain a boolean pass field.")
        return parsed["pass"]


@dataclass(frozen=True)
class VerifierCaseResult:
    case_id: str
    expected_pass: bool
    verifier_pass: bool
    matched_gold: bool


@dataclass(frozen=True)
class VerifierMetrics:
    evaluated_cases: int
    agreement_with_gold: float
    false_accept_rate: float | None
    false_reject_rate: float | None
    results: tuple[VerifierCaseResult, ...]


async def evaluate_answer_verifier(
    verifier: AnswerVerifier,
    cases: Sequence[MultiHopGoldCase],
    answer_results: Sequence[MultiHopCaseResult],
) -> VerifierMetrics:
    """Compare an independent verifier with deterministic gold-based scoring."""
    case_by_id = {case.case_id: case for case in cases}
    if set(case_by_id) != {result.case_id for result in answer_results}:
        raise ValueError("Verifier cases and answer results must have the same IDs.")

    results: list[VerifierCaseResult] = []
    matches = 0
    expected_failures = 0
    false_accepts = 0
    expected_passes = 0
    false_rejects = 0
    for answer_result in answer_results:
        case = case_by_id[answer_result.case_id]
        verifier_pass = await verifier.verify(
            question=case.question,
            required_facts=case.required_facts,
            should_abstain=case.should_abstain,
            answer=answer_result.answer,
        )
        expected_pass = answer_result.answer_passed
        matched = verifier_pass == expected_pass
        matches += int(matched)
        if expected_pass:
            expected_passes += 1
            false_rejects += int(not verifier_pass)
        else:
            expected_failures += 1
            false_accepts += int(verifier_pass)
        results.append(
            VerifierCaseResult(
                case_id=case.case_id,
                expected_pass=expected_pass,
                verifier_pass=verifier_pass,
                matched_gold=matched,
            )
        )

    return VerifierMetrics(
        evaluated_cases=len(results),
        agreement_with_gold=matches / len(results),
        false_accept_rate=(
            false_accepts / expected_failures if expected_failures else None
        ),
        false_reject_rate=(false_rejects / expected_passes if expected_passes else None),
        results=tuple(results),
    )
