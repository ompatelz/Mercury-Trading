"""Append-only decision ledger and deterministic replay helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.governance import DecisionRecord, DecisionRuleEvaluation


class DecisionService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        decision_type: str,
        outcome: str,
        actor: str,
        reason: str,
        rules: list[dict[str, Any]] | None = None,
        campaign_id: UUID | None = None,
        experiment_id: UUID | None = None,
        strategy_id: UUID | None = None,
        workflow_experiment_id: UUID | None = None,
        correlation_id: str | None = None,
        inputs: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
        alternatives: list[dict[str, Any]] | None = None,
        provenance: dict[str, Any] | None = None,
        versions: dict[str, Any] | None = None,
        supersedes_id: UUID | None = None,
    ) -> DecisionRecord:
        normalized_rules = sorted(
            (_normalize_rule(item) for item in (rules or [])),
            key=lambda item: item["rule"],
        )
        payload = {
            "decision_type": decision_type,
            "outcome": outcome,
            "actor": actor,
            "reason": reason,
            "inputs": inputs or {},
            "metrics": metrics or {},
            "alternatives": alternatives or [],
            "provenance": provenance or {},
            "versions": versions or {},
            "rules": normalized_rules,
        }
        record = DecisionRecord(
            decision_type=decision_type,
            outcome=outcome,
            actor=actor,
            reason=reason,
            campaign_id=campaign_id,
            experiment_id=experiment_id,
            strategy_id=strategy_id,
            workflow_experiment_id=workflow_experiment_id,
            correlation_id=correlation_id
            or str(campaign_id or experiment_id or strategy_id or uuid4()),
            inputs=payload["inputs"],
            metrics=payload["metrics"],
            alternatives=payload["alternatives"],
            provenance=payload["provenance"],
            versions=payload["versions"],
            content_hash="pending",
            supersedes_id=supersedes_id,
        )
        self.session.add(record)
        self.session.flush()
        rule_rows = [
            DecisionRuleEvaluation(
                decision_id=record.id,
                rule=item["rule"],
                rule_version=item["rule_version"],
                threshold=item.get("threshold"),
                observed_value=item.get("observed_value"),
                passed=item["passed"],
                detail=item.get("detail"),
            )
            for item in normalized_rules
        ]
        self.session.add_all(rule_rows)
        self.session.flush()
        self.session.expire(
            record,
            ["inputs", "metrics", "alternatives", "provenance", "versions"],
        )
        for row in rule_rows:
            self.session.expire(row)
        record.content_hash = _hash(_payload_for_hash(record, self.rules(record.id)))
        self.session.flush()
        return record

    def get(self, decision_id: UUID) -> DecisionRecord | None:
        return self.session.get(DecisionRecord, decision_id)

    def list_decisions(
        self,
        *,
        campaign_id: UUID | None = None,
        experiment_id: UUID | None = None,
        strategy_id: UUID | None = None,
        decision_type: str | None = None,
        outcome: str | None = None,
    ) -> list[DecisionRecord]:
        statement = select(DecisionRecord).order_by(DecisionRecord.created_at.desc())
        filters = (
            (DecisionRecord.campaign_id, campaign_id),
            (DecisionRecord.experiment_id, experiment_id),
            (DecisionRecord.strategy_id, strategy_id),
            (DecisionRecord.decision_type, decision_type),
            (DecisionRecord.outcome, outcome),
        )
        for column, value in filters:
            if value is not None:
                statement = statement.where(column == value)
        return list(self.session.scalars(statement))

    def rules(self, decision_id: UUID) -> list[DecisionRuleEvaluation]:
        return list(
            self.session.scalars(
                select(DecisionRuleEvaluation)
                .where(DecisionRuleEvaluation.decision_id == decision_id)
                .order_by(DecisionRuleEvaluation.rule)
            )
        )

    def explain(self, decision_id: UUID) -> dict[str, Any] | None:
        record = self.get(decision_id)
        if record is None:
            return None
        rules = self.rules(record.id)
        recomputed_hash = _hash(_payload_for_hash(record, rules))
        return {
            **record_to_dict(record),
            "rules": [_rule_dict(rule) for rule in rules],
            "integrity": {
                "content_hash": record.content_hash,
                "verified": recomputed_hash == record.content_hash,
            },
        }


def record_to_dict(record: DecisionRecord) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "decision_type": record.decision_type,
        "outcome": record.outcome,
        "actor": record.actor,
        "reason": record.reason,
        "campaign_id": _id(record.campaign_id),
        "experiment_id": _id(record.experiment_id),
        "strategy_id": _id(record.strategy_id),
        "workflow_experiment_id": _id(record.workflow_experiment_id),
        "correlation_id": record.correlation_id,
        "inputs": record.inputs,
        "metrics": record.metrics,
        "alternatives": record.alternatives,
        "provenance": record.provenance,
        "versions": record.versions,
        "content_hash": record.content_hash,
        "supersedes_id": _id(record.supersedes_id),
        "created_at": record.created_at,
    }


def _rule_dict(rule: DecisionRuleEvaluation) -> dict[str, Any]:
    return {
        "rule": rule.rule,
        "rule_version": rule.rule_version,
        "threshold": rule.threshold,
        "observed_value": rule.observed_value,
        "passed": rule.passed,
        "detail": rule.detail,
    }


def _payload_for_hash(
    record: DecisionRecord, rules: list[DecisionRuleEvaluation]
) -> dict[str, Any]:
    return {
        "decision_type": record.decision_type,
        "outcome": record.outcome,
        "actor": record.actor,
        "reason": record.reason,
        "inputs": record.inputs,
        "metrics": record.metrics,
        "alternatives": record.alternatives,
        "provenance": record.provenance,
        "versions": record.versions,
        "rules": [_rule_dict(rule) for rule in sorted(rules, key=lambda item: item.rule)],
    }


def _normalize_rule(rule: dict[str, Any]) -> dict[str, Any]:
    return {
        "rule": str(rule["rule"]),
        "rule_version": str(rule.get("rule_version", "v1")),
        "threshold": rule.get("threshold"),
        "observed_value": rule.get("observed_value"),
        "passed": bool(rule["passed"]),
        "detail": rule.get("detail"),
    }


def _id(value: UUID | None) -> str | None:
    return str(value) if value else None


def _hash(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()
