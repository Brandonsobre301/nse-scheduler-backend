"""
estimation.py — Pydantic v2 request/response schemas for the estimation engine.

These schemas define the strict API contract between the Node.js orchestrator
and the FastAPI estimation service as specified in the Estimation Engine spec §4.

Key contract rules enforced here:
  - calculationMode must be exactly "duration" or "manpower" (Literal type)
  - Unused output fields are returned as None rather than omitted (stable schema)
  - assumedEfficiency is required in Phase 1; Phase 2 will make it optional
    when the LangChain agent computes it from historical data
  - The warnings list is always present (empty in Phase 1, populated in Phase 2)
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class EstimationInputs(BaseModel):
    totalManHours: float = Field(
        ...,
        gt=0,
        description="Total man-hours bid on the project (MH)",
    )
    desiredManpower: Optional[int] = Field(
        default=None,
        gt=0,
        description="Desired crew size — required for 'duration' mode (MP)",
    )
    targetDurationWeeks: Optional[float] = Field(
        default=None,
        gt=0,
        description="Hard deadline in weeks — required for 'manpower' mode (TD)",
    )
    # Optional in Phase 2: when omitted the LangChain efficiency agent infers
    # this value from similar historical projects in MongoDB Atlas.
    assumedEfficiency: Optional[float] = Field(
        default=None,
        gt=0,
        le=2.0,
        description=(
            "Assumed efficiency as a decimal (e.g. 0.85 = 85%). "
            "If omitted, the AI agent infers it from historical project data."
        ),
    )
    # Contextual fields used by the efficiency agent when assumedEfficiency is None
    projectType: Optional[str] = Field(
        default=None,
        description="Type of project — improves AI efficiency inference accuracy",
    )
    supervisor: Optional[str] = Field(
        default=None,
        description="Supervisor name — improves AI efficiency inference accuracy",
    )
    jobName: Optional[str] = Field(
        default=None,
        description="Job name — optional additional signal for AI inference",
    )


class EstimationRequest(BaseModel):
    projectId: str = Field(
        ...,
        min_length=1,
        description="Identifier of the project being estimated",
    )
    calculationMode: Literal["duration", "manpower"] = Field(
        ...,
        description="'duration' — calculate how long; 'manpower' — calculate crew size",
    )
    inputs: EstimationInputs

    @model_validator(mode="after")
    def check_mode_inputs(self) -> EstimationRequest:
        """Raise 400-compatible ValueError if required inputs for the selected mode are None."""
        mode = self.calculationMode
        inputs = self.inputs

        if mode == "duration" and inputs.desiredManpower is None:
            raise ValueError(
                "desiredManpower is required when calculationMode is 'duration'."
            )
        if mode == "manpower" and inputs.targetDurationWeeks is None:
            raise ValueError(
                "targetDurationWeeks is required when calculationMode is 'manpower'."
            )
        return self


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class EstimationOutputs(BaseModel):
    # Mode 1 outputs — null when mode is "manpower"
    realisticDurationWeeks: Optional[float] = None
    totalExpendedHours: Optional[float] = None

    # Mode 2 outputs — null when mode is "duration"
    recommendedManpower: Optional[int] = None

    # Present in both modes
    calculatedEfficiency: float
    efficiencySource: str = "provided"  # "provided" | "agent_inferred" | "fallback_default"
    warnings: list[str] = Field(default_factory=list)

    # Phase 2 — agent inference evidence (null when efficiency was user-provided)
    inferenceMatchCount: Optional[int] = None
    inferenceConfidence: Optional[float] = None
    inferenceEvidence: Optional[list[dict]] = None


class EstimationResponse(BaseModel):
    status: Literal["success"] = "success"
    projectId: str
    calculationMode: Literal["duration", "manpower"]
    outputs: EstimationOutputs


# ---------------------------------------------------------------------------
# Error response schema
# ---------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    status: Literal["error"] = "error"
    message: str
    field: Optional[str] = None
