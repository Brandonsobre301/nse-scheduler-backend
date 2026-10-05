"""
test_estimate_router.py — full API contract tests via FastAPI TestClient.

Traceability: docs/estimation-engine/test_plan.md §6.3, 6.4, 6.5 (schema-level
guardrails, inference wiring, response shape stability). See spec.md §4 for
why several guardrail cases assert 422 rather than test_plan.md's original 400.
"""

import os

os.environ.setdefault("AI_SERVICE_API_KEY", "test-internal-key")

from fastapi.testclient import TestClient

import routers.estimate as estimate_router
from main import app
from services.efficiency_agent import EfficiencyInferenceResult

client = TestClient(app)
HEADERS = {"X-Internal-Api-Key": "test-internal-key"}


def _body(mode, **inputs):
    return {"projectId": "PROJ-1", "calculationMode": mode, "inputs": inputs}


# ---------------------------------------------------------------------------
# Internal auth boundary (defense in depth on top of Docker isolation + JWT)
# ---------------------------------------------------------------------------

def test_missing_internal_key_is_rejected():
    resp = client.post(
        "/api/v1/estimate",
        json=_body("duration", totalManHours=4800, desiredManpower=6, assumedEfficiency=1.0),
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Response schema stability — TC-S01, TC-S02, TC-S03
# ---------------------------------------------------------------------------

def test_duration_mode_nulls_manpower_field():  # TC-S01
    resp = client.post("/api/v1/estimate", headers=HEADERS, json=_body(
        "duration", totalManHours=4800, desiredManpower=6, assumedEfficiency=0.85
    ))
    assert resp.status_code == 200
    out = resp.json()["outputs"]
    assert out["recommendedManpower"] is None
    assert out["realisticDurationWeeks"] is not None
    assert out["totalExpendedHours"] is not None
    assert out["efficiencySource"] == "provided"
    assert out["warnings"] == []
    assert out["inferenceMatchCount"] is None  # TC-A06 — inference skipped entirely


def test_manpower_mode_nulls_duration_fields():  # TC-S02
    resp = client.post("/api/v1/estimate", headers=HEADERS, json=_body(
        "manpower", totalManHours=4800, targetDurationWeeks=20, assumedEfficiency=0.9
    ))
    assert resp.status_code == 200
    out = resp.json()["outputs"]
    assert out["realisticDurationWeeks"] is None
    assert out["totalExpendedHours"] is None
    assert out["recommendedManpower"] == 7


def test_warnings_is_always_a_list():  # TC-S03
    resp = client.post("/api/v1/estimate", headers=HEADERS, json=_body(
        "duration", totalManHours=4800, desiredManpower=6, assumedEfficiency=1.0
    ))
    assert isinstance(resp.json()["outputs"]["warnings"], list)


# ---------------------------------------------------------------------------
# Guardrails — actual HTTP status codes (see spec.md §4)
# ---------------------------------------------------------------------------

def test_total_man_hours_zero_is_422():  # TC-G01
    resp = client.post("/api/v1/estimate", headers=HEADERS, json=_body(
        "duration", totalManHours=0, desiredManpower=6, assumedEfficiency=1.0
    ))
    assert resp.status_code == 422


def test_efficiency_above_2_is_422_not_400():  # TC-G06 (corrects test_plan.md)
    resp = client.post("/api/v1/estimate", headers=HEADERS, json=_body(
        "duration", totalManHours=4800, desiredManpower=6, assumedEfficiency=2.5
    ))
    assert resp.status_code == 422


def test_desired_manpower_missing_in_duration_mode_is_422():  # TC-G08 (corrects test_plan.md)
    resp = client.post("/api/v1/estimate", headers=HEADERS, json=_body(
        "duration", totalManHours=4800, assumedEfficiency=1.0
    ))
    assert resp.status_code == 422


def test_target_duration_missing_in_manpower_mode_is_422():  # TC-G09 (corrects test_plan.md)
    resp = client.post("/api/v1/estimate", headers=HEADERS, json=_body(
        "manpower", totalManHours=4800, assumedEfficiency=1.0
    ))
    assert resp.status_code == 422


def test_invalid_calculation_mode_is_422():  # TC-G10
    resp = client.post("/api/v1/estimate", headers=HEADERS, json=_body(
        "speed", totalManHours=4800, assumedEfficiency=1.0
    ))
    assert resp.status_code == 422


def test_missing_project_id_is_422():  # TC-G11
    payload = _body("duration", totalManHours=4800, desiredManpower=6, assumedEfficiency=1.0)
    payload["projectId"] = ""
    resp = client.post("/api/v1/estimate", headers=HEADERS, json=payload)
    assert resp.status_code == 422


def test_wrong_type_is_422():  # TC-G12
    resp = client.post("/api/v1/estimate", headers=HEADERS, json=_body(
        "duration", totalManHours="abc", desiredManpower=6, assumedEfficiency=1.0
    ))
    assert resp.status_code == 422


def test_ai_inferred_efficiency_out_of_range_is_400(monkeypatch):
    # The only realistic path to the engine's own ValueError guardrail: the
    # schema only validates caller-supplied assumedEfficiency, not the agent's
    # inferred value.
    monkeypatch.setattr(
        estimate_router,
        "infer_efficiency",
        lambda **kwargs: EfficiencyInferenceResult(
            inferredEfficiency=3.0, confidence=0.9, matchCount=2, evidence=[],
        ),
    )
    resp = client.post("/api/v1/estimate", headers=HEADERS, json=_body(
        "duration", totalManHours=4800, desiredManpower=6
    ))
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# AI inference wiring — TC-A06 (skip) and agent_inferred path
# ---------------------------------------------------------------------------

def test_assumed_efficiency_provided_skips_inference(monkeypatch):  # TC-A06
    called = False

    def _spy(**kwargs):
        nonlocal called
        called = True
        raise AssertionError("infer_efficiency should not be called when assumedEfficiency is provided")

    monkeypatch.setattr(estimate_router, "infer_efficiency", _spy)
    resp = client.post("/api/v1/estimate", headers=HEADERS, json=_body(
        "duration", totalManHours=4800, desiredManpower=6, assumedEfficiency=0.85
    ))
    assert resp.status_code == 200
    assert called is False
    out = resp.json()["outputs"]
    assert out["efficiencySource"] == "provided"
    assert out["inferenceEvidence"] is None


def test_assumed_efficiency_omitted_uses_agent_inferred(monkeypatch):
    monkeypatch.setattr(
        estimate_router,
        "infer_efficiency",
        lambda **kwargs: EfficiencyInferenceResult(
            inferredEfficiency=0.79, confidence=0.81, matchCount=5,
            evidence=[{"jobNumber": "2144"}],
        ),
    )
    resp = client.post("/api/v1/estimate", headers=HEADERS, json=_body(
        "manpower", totalManHours=4800, targetDurationWeeks=20, projectType="Office TI"
    ))
    assert resp.status_code == 200
    out = resp.json()["outputs"]
    assert out["efficiencySource"] == "agent_inferred"
    assert out["calculatedEfficiency"] == 0.79
    assert out["inferenceMatchCount"] == 5


def test_no_historical_matches_uses_fallback_default(monkeypatch):
    monkeypatch.setattr(
        estimate_router,
        "infer_efficiency",
        lambda **kwargs: EfficiencyInferenceResult(
            inferredEfficiency=0.80, confidence=0.0, matchCount=0, evidence=[],
            warning="No similar historical projects found.",
        ),
    )
    resp = client.post("/api/v1/estimate", headers=HEADERS, json=_body(
        "manpower", totalManHours=4800, targetDurationWeeks=20
    ))
    assert resp.status_code == 200
    out = resp.json()["outputs"]
    assert out["efficiencySource"] == "fallback_default"
    assert any("No similar historical projects" in w for w in out["warnings"])
