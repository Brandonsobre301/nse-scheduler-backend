"""
estimate.py — FastAPI router for POST /api/v1/estimate

Wires the Pydantic request/response schemas to the estimation engine.
Handles semantic validation errors (missing mode-required inputs) as HTTP 400,
while letting FastAPI/Pydantic handle type validation errors as HTTP 422.

Phase 2: when assumedEfficiency is omitted, the efficiency agent queries
MongoDB Atlas Vector Search to infer it from similar historical projects.

Internal service only — no auth here. Authentication is enforced by the
Node.js backend before it proxies requests to this service.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from models.estimation import (
    EstimationRequest,
    EstimationResponse,
    EstimationOutputs,
    ErrorDetail,
)
from services.estimation_engine import calculate_duration, calculate_manpower
from services.efficiency_agent import infer_efficiency

router = APIRouter()


@router.post(
    "/estimate",
    response_model=EstimationResponse,
    responses={
        400: {"model": ErrorDetail, "description": "Missing required inputs for selected mode"},
        422: {"description": "Request body failed schema validation"},
    },
    summary="Run a labor estimation calculation",
    description=(
        "Accepts a project ID, calculation mode, and input parameters. "
        "If assumedEfficiency is omitted, the AI agent infers it from similar "
        "historical projects via Atlas Vector Search."
    ),
)
async def estimate(request: EstimationRequest) -> EstimationResponse:
    """
    POST /api/v1/estimate

    Mode 'duration': returns realisticDurationWeeks + totalExpendedHours
    Mode 'manpower': returns recommendedManpower
    Unused output fields are explicitly null (not omitted).
    """
    try:
        # ----------------------------------------------------------------
        # Phase 2: resolve efficiency — agent or user-provided
        # ----------------------------------------------------------------
        inference_result = None
        efficiency_source = "provided"

        if request.inputs.assumedEfficiency is None:
            inference_result = infer_efficiency(
                project_type=request.inputs.projectType,
                budgeted_hrs=request.inputs.totalManHours,
                supervisor=request.inputs.supervisor,
                job_name=request.inputs.jobName,
            )
            resolved_efficiency = inference_result.inferredEfficiency
            efficiency_source = (
                "fallback_default" if inference_result.matchCount == 0
                else "agent_inferred"
            )
        else:
            resolved_efficiency = request.inputs.assumedEfficiency

        # ----------------------------------------------------------------
        # Run the deterministic calculation with the resolved efficiency
        # ----------------------------------------------------------------
        warnings: list[str] = []
        if inference_result and inference_result.warning:
            warnings.append(inference_result.warning)

        if request.calculationMode == "duration":
            result = calculate_duration(
                total_man_hours=request.inputs.totalManHours,
                desired_manpower=request.inputs.desiredManpower,
                assumed_efficiency=resolved_efficiency,
            )
            warnings.extend(result.warnings)
            outputs = EstimationOutputs(
                realisticDurationWeeks=result.realisticDurationWeeks,
                totalExpendedHours=result.totalExpendedHours,
                recommendedManpower=None,
                calculatedEfficiency=result.calculatedEfficiency,
                efficiencySource=efficiency_source,
                warnings=warnings,
                inferenceMatchCount=inference_result.matchCount if inference_result else None,
                inferenceConfidence=inference_result.confidence if inference_result else None,
                inferenceEvidence=inference_result.evidence if inference_result else None,
            )

        else:  # calculationMode == "manpower"
            result = calculate_manpower(
                total_man_hours=request.inputs.totalManHours,
                target_duration_weeks=request.inputs.targetDurationWeeks,
                assumed_efficiency=resolved_efficiency,
            )
            warnings.extend(result.warnings)
            outputs = EstimationOutputs(
                realisticDurationWeeks=None,
                totalExpendedHours=None,
                recommendedManpower=result.recommendedManpower,
                calculatedEfficiency=result.calculatedEfficiency,
                efficiencySource=efficiency_source,
                warnings=warnings,
                inferenceMatchCount=inference_result.matchCount if inference_result else None,
                inferenceConfidence=inference_result.confidence if inference_result else None,
                inferenceEvidence=inference_result.evidence if inference_result else None,
            )

    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content=ErrorDetail(message=str(exc)).model_dump(),
        )

    return EstimationResponse(
        projectId=request.projectId,
        calculationMode=request.calculationMode,
        outputs=outputs,
    )
