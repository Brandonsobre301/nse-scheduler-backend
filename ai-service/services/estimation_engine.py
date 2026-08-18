"""
estimation_engine.py — NSE Scheduler Estimation Brain (Phase 1: Deterministic)

Implements the two calculation modes defined in the Estimation Engine spec.
This module is pure Python with no framework dependencies — it can be unit-tested
directly without standing up the FastAPI service.

Mode 1 — Calculate Duration
    Given: totalManHours (MH), desiredManpower (MP), assumedEfficiency (E)
    Returns: realisticDurationWeeks (RD), totalExpendedHours (EH)

Mode 2 — Calculate Manpower
    Given: totalManHours (MH), targetDurationWeeks (TD), assumedEfficiency (E)
    Returns: recommendedManpower (RM)

Phase 2 hooks (not yet implemented):
    - efficiency_agent.py will replace the static assumedEfficiency input with a
      dynamically computed value derived from historicalProjects records.
    - Labor density conflict detection will populate the warnings list after
      recommendedManpower is computed.
    - Ceiling delta compensation will compute the adjusted completion date caused
      by the surplus labor fraction introduced by math.ceil().
"""

import math
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Result dataclasses — decoupled from Pydantic so the engine stays testable
# ---------------------------------------------------------------------------

@dataclass
class DurationResult:
    realisticDurationWeeks: float
    totalExpendedHours: float
    calculatedEfficiency: float
    warnings: list[str] = field(default_factory=list)

    # Phase 2: ceiling delta compensation will add this field
    # adjustedCompletionWeeks: float | None = None


@dataclass
class ManpowerResult:
    recommendedManpower: int
    exactManpower: float          # MP_f before ceiling — exposed for Phase 2 delta calc
    calculatedEfficiency: float
    warnings: list[str] = field(default_factory=list)

    # Phase 2: ceiling delta compensation
    # ceilingDeltaWeeks: float | None = None  # how many weeks ahead of deadline
    # revisedCompletionWeeks: float | None = None


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _require_positive(value: float, name: str) -> None:
    if value is None:
        raise ValueError(f"{name} is required for this calculation mode.")
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero. Got: {value}")


def _require_efficiency(e: float) -> None:
    if e is None:
        raise ValueError("assumedEfficiency is required.")
    if not (0 < e <= 2.0):
        raise ValueError(
            f"assumedEfficiency must be between 0 (exclusive) and 2.0 (inclusive). Got: {e}"
        )


# ---------------------------------------------------------------------------
# Mode 1 — Calculate Duration
# ---------------------------------------------------------------------------

def calculate_duration(
    total_man_hours: float,
    desired_manpower: int,
    assumed_efficiency: float,
) -> DurationResult:
    """
    Given a fixed crew size, calculate how long the project will take and the
    total labor hours expended accounting for efficiency loss.

    Formula:
        MW  = MH / 40                  (man-weeks of work)
        IW  = MW / MP                  (ideal weeks at 100% efficiency)
        RD  = IW / E                   (realistic duration after efficiency loss)
        EH  = RD × MP × 40            (total expended hours)

    Args:
        total_man_hours:    Total man-hours bid on the project (MH)
        desired_manpower:   Crew size (MP) — number of workers on site
        assumed_efficiency: Efficiency decimal e.g. 0.85 = 85% (E)

    Returns:
        DurationResult with realisticDurationWeeks and totalExpendedHours
    """
    _require_positive(total_man_hours, "totalManHours")
    _require_positive(desired_manpower, "desiredManpower")
    _require_efficiency(assumed_efficiency)

    man_weeks: float = total_man_hours / 40
    ideal_weeks: float = man_weeks / desired_manpower
    realistic_duration: float = ideal_weeks / assumed_efficiency
    expended_hours: float = realistic_duration * desired_manpower * 40

    return DurationResult(
        realisticDurationWeeks=round(realistic_duration, 2),
        totalExpendedHours=round(expended_hours, 2),
        calculatedEfficiency=assumed_efficiency,
    )


# ---------------------------------------------------------------------------
# Mode 2 — Calculate Manpower
# ---------------------------------------------------------------------------

def calculate_manpower(
    total_man_hours: float,
    target_duration_weeks: float,
    assumed_efficiency: float,
) -> ManpowerResult:
    """
    Given a hard deadline, calculate the minimum crew size required to meet it.

    Formula:
        MW    = MH / 40                (man-weeks of work)
        EW    = TD × E                 (effective productive weeks within deadline)
        MP_f  = MW / EW                (exact manpower — will be fractional)
        RM    = ⌈MP_f⌉                 (ceiling — always round up, never down)

    Why ceiling? Rounding down would leave the project incomplete by the deadline.
    The ceiling introduces a fractional surplus worker whose impact is tracked in
    Phase 2 via ceiling delta compensation.

    Args:
        total_man_hours:        Total man-hours bid on the project (MH)
        target_duration_weeks:  Hard deadline in weeks (TD)
        assumed_efficiency:     Efficiency decimal e.g. 0.85 = 85% (E)

    Returns:
        ManpowerResult with recommendedManpower (RM) and exactManpower (MP_f)
    """
    _require_positive(total_man_hours, "totalManHours")
    _require_positive(target_duration_weeks, "targetDurationWeeks")
    _require_efficiency(assumed_efficiency)

    man_weeks: float = total_man_hours / 40
    effective_weeks: float = target_duration_weeks * assumed_efficiency
    exact_manpower: float = man_weeks / effective_weeks
    recommended_manpower: int = math.ceil(exact_manpower)

    # Phase 2 hook: ceiling delta
    # If exact_manpower is already a whole number, ceiling introduces no delta.
    # Otherwise the surplus fraction means the crew finishes ahead of deadline.
    # ceiling_delta_weeks = target_duration_weeks - (man_weeks / (recommended_manpower * assumed_efficiency))

    return ManpowerResult(
        recommendedManpower=recommended_manpower,
        exactManpower=round(exact_manpower, 4),
        calculatedEfficiency=assumed_efficiency,
    )
