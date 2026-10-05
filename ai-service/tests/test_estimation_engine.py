"""
test_estimation_engine.py — unit tests for the pure calculation engine.

Traceability: docs/estimation-engine/test_plan.md §6.1-6.3 (TC-D*, TC-M*, TC-G*).
These exercise estimation_engine.py functions directly — no FastAPI, no DB.
"""

import pytest

from services.estimation_engine import calculate_duration, calculate_manpower


# ---------------------------------------------------------------------------
# Mode 1 — Calculate Duration
# ---------------------------------------------------------------------------

def test_duration_baseline_efficiency():  # TC-D01
    r = calculate_duration(4800, 6, 1.0)
    assert r.realisticDurationWeeks == 20.0
    assert r.totalExpendedHours == 4800.0


def test_duration_inefficient_crew():  # TC-D02
    r = calculate_duration(4800, 6, 0.8)
    assert r.realisticDurationWeeks == 25.0
    assert r.totalExpendedHours == 6000.0


def test_duration_overperforming_crew():  # TC-D03
    # NOTE: corrects test_plan.md's stale expected EH of 4800 — the formula
    # EH = H / E gives 4800 / 1.2 = 4000.0, confirmed here against actual code.
    r = calculate_duration(4800, 6, 1.2)
    assert r.realisticDurationWeeks == 16.67
    assert r.totalExpendedHours == 4000.0


def test_duration_results_rounded_to_2dp():  # TC-D04
    r = calculate_duration(1000, 3, 0.73)
    assert r.realisticDurationWeeks == round(r.realisticDurationWeeks, 2)
    assert r.totalExpendedHours == round(r.totalExpendedHours, 2)


# ---------------------------------------------------------------------------
# Mode 2 — Calculate Manpower
# ---------------------------------------------------------------------------

def test_manpower_exact_whole_number():  # TC-M01
    r = calculate_manpower(4800, 20, 1.0)
    assert r.recommendedManpower == 6
    assert r.exactManpower == 6.0


def test_manpower_rounds_up_never_down():  # TC-M02
    r = calculate_manpower(4800, 20, 0.9)
    assert r.exactManpower == pytest.approx(6.6667, abs=1e-4)
    assert r.recommendedManpower == 7  # never 6 — ceiling, not round()


def test_manpower_exact_value_rounded_to_4dp():  # TC-M03
    r = calculate_manpower(1000, 7, 0.65)
    assert r.exactManpower == round(r.exactManpower, 4)


# ---------------------------------------------------------------------------
# Guardrails (engine-level — defense in depth; see spec.md §4 for which of
# these are actually reachable through the live HTTP API vs. intercepted
# earlier by the Pydantic schema).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hours", [0, -100])
def test_guardrail_total_man_hours_must_be_positive(hours):  # TC-G01, TC-G02
    with pytest.raises(ValueError, match="totalManHours"):
        calculate_duration(hours, 6, 1.0)


def test_guardrail_desired_manpower_zero():  # TC-G03
    with pytest.raises(ValueError, match="desiredManpower"):
        calculate_duration(4800, 0, 1.0)


def test_guardrail_target_duration_zero():  # TC-G04
    with pytest.raises(ValueError, match="targetDurationWeeks"):
        calculate_manpower(4800, 0, 1.0)


def test_guardrail_efficiency_zero():  # TC-G05
    with pytest.raises(ValueError, match="assumedEfficiency"):
        calculate_duration(4800, 6, 0)


def test_guardrail_efficiency_above_2():  # TC-G06
    with pytest.raises(ValueError, match="assumedEfficiency"):
        calculate_duration(4800, 6, 2.5)


def test_guardrail_efficiency_exactly_2_is_accepted():  # TC-G07 (inclusive boundary)
    r = calculate_duration(4800, 6, 2.0)
    assert r.calculatedEfficiency == 2.0
