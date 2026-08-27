from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.governance.service import DecisionService


def test_decision_api_and_campaign_timeline(client: TestClient, db_session: Session) -> None:
    campaign_id = uuid4()
    decision = DecisionService(db_session).record(
        decision_type="CAMPAIGN_PLAN",
        outcome="PLANNED",
        actor="test",
        reason="campaign plan fixture",
        campaign_id=campaign_id,
        inputs={"objective": "fixture"},
        rules=[{"rule": "BUDGET_LIMIT", "observed_value": 1, "threshold": 2, "passed": True}],
    )
    db_session.commit()

    decision_response = client.get(f"/decisions/{decision.id}")
    assert decision_response.status_code == 200
    payload = decision_response.json()
    assert payload["decision_type"] == "CAMPAIGN_PLAN"
    assert payload["integrity"]["verified"] is True
    assert payload["rules"][0]["rule"] == "BUDGET_LIMIT"

    list_response = client.get("/decisions?decision_type=CAMPAIGN_PLAN")
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == str(decision.id)

    timeline_response = client.get(f"/campaigns/{campaign_id}/timeline")
    assert timeline_response.status_code == 200
    assert timeline_response.json()[0]["id"] == str(decision.id)
