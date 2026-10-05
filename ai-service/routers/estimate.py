"""
estimate.py — FastAPI router for POST /api/v1/estimate

Wires the Pydantic request/response schemas to the estimation engine.
Handles semantic validation errors (missing mode-required inputs) as HTTP 400,
while letting FastAPI/Pydantic handle type validation errors as HTTP 422.

Phase 2: when assumedEfficiency is omitted, the efficiency agent queries
MongoDB Atlas Vector Search to infer it from similar historical projects.

Docker network isolation (app-net, port 8000 not published) is the primary
boundary control, but `verify_internal_key` is a defense-in-depth check in
case this service is ever reachable from elsewhere on the network — it does
NOT replace the Node.js JWT auth enforced before requests reach here.
"""

import logging
import os

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse

from models.estimation import (
    EstimationRequest,
    EstimationResponse,
    EstimationOutputs,
    ErrorDetail,
)
from services.estimation_engine import calculate_duration, calculate_manpower
from services.efficiency_agent import infer_efficiency

logger = logging.getLogger(__name__)

router = APIRouter()

INTERNAL_API_KEY = os.getenv("AI_SERVICE_API_KEY")


async def verify_internal_key(x_internal_api_key: str | None = Header(default=None)) -> None:
    if not INTERNAL_API_KEY:
        # Fail closed rather than silently accepting unauthenticated traffic.
        raise HTTPException(status_code=503, detail="Service misconfigured")
    if x_internal_api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post(
    "/estimate",
    response_model=EstimationResponse,
    dependencies=[Depends(verify_internal_key)],
    responses={
        400: {"model": ErrorDetail, "description": "Missing required inputs for selected mode"},
        401: {"description": "Missing or invalid internal service credential"},
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
    except Exception:
        # Never leak stack traces, DB errors, or connection strings to the client.
        logger.exception("Unhandled error computing estimate for project %s", request.projectId)
        return JSONResponse(
            status_code=500,
            content=ErrorDetail(
                message="An internal error occurred while processing the estimate."
            ).model_dump(),
        )

    return EstimationResponse(
        projectId=request.projectId,
        calculationMode=request.calculationMode,
        outputs=outputs,
    )
