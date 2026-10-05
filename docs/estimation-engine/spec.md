# Estimation Engine — Spec

> **Status:** Authoritative. This is the single source of truth for the estimation engine's
> behavior, contracts, and guardrails. `estimation_engine.py`, `efficiency_agent.py`,
> `models/estimation.py`, and `routers/estimate.py` docstrings reference this file by section
> number (e.g. "spec §4"). If code and this document ever disagree, **that is a bug** — fix
> whichever one is wrong, and update the other to match, in the same change.
>
> Companion documents: [test_plan.md](./test_plan.md) (test strategy/case catalogue, now
> partially automated — see §7 Traceability) and [user_manual.md](./user_manual.md)
> (user-facing walkthrough). Those two must never contradict this file.

## 1. Overview

The estimation engine answers two questions via a single endpoint, `POST /api/v1/estimate`,
reached only through the Express gateway (`routes/estimateRoutes.ts` → `ai-service:8000`,
never exposed directly):

- **Mode 1 — `duration`:** given a fixed crew size, how many weeks will the job take?
- **Mode 2 — `manpower`:** given a fixed deadline, how many workers are needed?

Both depend on an **efficiency** factor, either supplied by the caller or inferred by the
Phase 2 AI agent from historical project data (Atlas Vector Search).

## 2. Variables

| Symbol | Name | Type | Domain |
|---|---|---|---|
| `H` | `totalManHours` | float | `(0, 1,000,000]` |
| `MP` | `desiredManpower` | int | `(0, 10,000]`, required for `duration` mode |
| `T` | `targetDurationWeeks` | float | `(0, 1,000]`, required for `manpower` mode |
| `E` | `assumedEfficiency` | float | `(0, 2.0]`; optional — inferred by AI agent if omitted |

A 40-hour work-week is assumed throughout (`WEEK_HOURS = 40`, hardcoded).

## 3. Formulas (authoritative)

### Mode 1 — Calculate Duration

```
MW  = H / 40                   man-weeks of work
IW  = MW / MP                  ideal weeks at 100% efficiency
RD  = IW / E                   realistic duration            → realisticDurationWeeks
EH  = RD × MP × 40  (≡ H / E)  total expended hours           → totalExpendedHours
```

Both outputs are rounded to **2 decimal places**.

### Mode 2 — Calculate Manpower

```
MW    = H / 40                 man-weeks of work
EW    = T × E                  effective productive weeks within the deadline
MP_f  = MW / EW                exact (fractional) manpower
RM    = ceil(MP_f)             recommended manpower — ALWAYS rounds up, never down
```

`exactManpower` (`MP_f`) is rounded to **4 decimal places** and returned for transparency /
future "ceiling delta compensation" (tracked as a Phase 2+ enhancement, not yet implemented).

## 4. Validation & Guardrails — authoritative status codes

This corrects discrepancies found in `test_plan.md` v1 (confirmed by the automated suite in
`ai-service/tests/`, §7 below): the Pydantic schema (`EstimationInputs`/`EstimationRequest`)
enforces numeric ranges and mode-conditional requirements **before** the route handler or the
engine ever runs. The engine's own `_require_positive`/`_require_efficiency` checks are
defense-in-depth and are only reachable in practice when the **AI-inferred** efficiency falls
outside the valid range (the schema only validates a caller-supplied `assumedEfficiency`, not
the agent's output).

| Condition | Enforced by | Actual HTTP status |
|---|---|---|
| `totalManHours` ≤ 0 or > 1,000,000 | Pydantic `Field(gt=0, le=1_000_000)` | **422** |
| `desiredManpower` ≤ 0 or > 10,000 | Pydantic `Field(gt=0, le=10_000)` | **422** |
| `targetDurationWeeks` ≤ 0 or > 1,000 | Pydantic `Field(gt=0, le=1_000)` | **422** |
| `assumedEfficiency` ≤ 0 or > 2.0 (caller-supplied) | Pydantic `Field(gt=0, le=2.0)` | **422** |
| `desiredManpower` omitted, mode = `duration` | `EstimationRequest.check_mode_inputs` (`@model_validator`) | **422** (Pydantic wraps the `ValueError` into a `ValidationError`, not a raw 400) |
| `targetDurationWeeks` omitted, mode = `manpower` | same as above | **422** |
| `calculationMode` not `"duration"`/`"manpower"` | Pydantic `Literal[...]` | **422** |
| `projectId` missing/empty | Pydantic `Field(min_length=1)` | **422** |
| Wrong field type (e.g. `totalManHours: "abc"`) | Pydantic type coercion failure | **422** |
| **AI-inferred** efficiency ends up outside `(0, 2.0]` | `estimation_engine._require_efficiency`, caught by the router's `except ValueError` | **400** with `ErrorDetail` body |
| Missing/invalid internal service key (`X-Internal-Api-Key`) | `verify_internal_key` dependency | **401** (defense-in-depth; the real boundary is Docker network isolation + Express JWT) |
| Missing/invalid JWT | Express `auth` middleware | **401** (request never reaches `ai-service`) |
| `ai-service` unreachable | Express proxy `fetch` catch block | **503** |
| `ai-service` returns non-JSON body | Express proxy JSON parse catch block | **502** |

**Practical implication:** a 400 response from `/api/v1/estimate` today can only originate from
the AI-inference path producing an out-of-range value, never from a caller-supplied invalid
input (that's always 422). Client code must not assume 400 means "bad user input" — check the
`ErrorDetail.message`.

## 5. Response Schema Stability

`EstimationOutputs` always returns every field, using `null` for whichever mode's fields don't
apply (never omitted):

| Field | `duration` mode | `manpower` mode |
|---|---|---|
| `realisticDurationWeeks`, `totalExpendedHours` | value | `null` |
| `recommendedManpower` | `null` | value |
| `calculatedEfficiency`, `efficiencySource`, `warnings` | always present | always present |
| `inferenceMatchCount`, `inferenceConfidence`, `inferenceEvidence` | `null` when `assumedEfficiency` was caller-supplied | same |

`efficiencySource` is one of `"provided"` \| `"agent_inferred"` \| `"fallback_default"`.

## 6. AI Efficiency Inference (Phase 2)

Triggered only when `assumedEfficiency` is omitted.

1. Build query text: `f"{projectType or 'unknown type'}, {int(totalManHours)} hours budgeted, supervisor {supervisor or 'unknown supervisor'}[, {jobName}]"`.
2. Embed with `all-MiniLM-L6-v2`, run Atlas `$vectorSearch` (`historical_efficiency_index`,
   `numCandidates = k*10`, `limit = k = 5`) over `historicalProjects`.
3. Discard matches with `score < MIN_SCORE (0.50)` or missing `actualEfficiency`.
4. **No valid matches:** `inferredEfficiency = 0.80`, `confidence = 0.0`, `matchCount = 0`,
   `efficiencySource = "fallback_default"`, warning present.
5. **≥1 valid match:** weighted average of `actualEfficiency`, weight = similarity `score`.
   `efficiencySource = "agent_inferred"`. Warnings: `matchCount < 3` → "Only N similar
   project(s) found..."; else mean confidence `< 0.70` → "Similarity confidence is
   moderate...".

The query-text template in `efficiency_agent._build_query_text` must stay semantically
consistent with `embedder.build_embed_text` — if one changes, update both and re-ingest.

## 7. Test Suite & Traceability

Automated tests live in `ai-service/tests/` (pytest) and `routes/estimateRoutes.test.ts`
(Node's built-in test runner — no extra npm dependency). Run with:

```bash
# Python (from ai-service/, after: pip install -r requirements-dev.txt)
pytest

# Node proxy layer (from repo root)
npm test
```

| Spec area | Test file | Representative test IDs (from test_plan.md) |
|---|---|---|
| Mode 1 formulas | `ai-service/tests/test_estimation_engine.py` | TC-D01–TC-D04 |
| Mode 2 formulas | `ai-service/tests/test_estimation_engine.py` | TC-M01–TC-M03 |
| Engine-level guardrails (unit) | `ai-service/tests/test_estimation_engine.py` | TC-G01–TC-G07 |
| AI inference math/fallback/warnings | `ai-service/tests/test_efficiency_agent.py` | TC-A01–TC-A05 |
| Full API contract incl. real HTTP status codes | `ai-service/tests/test_estimate_router.py` | TC-G06,G08–G12, TC-S01–TC-S03, TC-A06 |
| Express proxy / auth boundary | `routes/estimateRoutes.test.ts` | TC-P01, TC-P03, TC-P04 |

Heavy ML/DB dependencies (`pymongo`, `sentence-transformers`) are stubbed in
`ai-service/tests/conftest.py` so the suite runs fast with no Atlas connection or model
download. Tests that need the *real* Atlas index/model belong in a separate, explicitly
marked integration suite — not yet built; out of scope until there's a seeded test cluster.

## 8. Change Control

Any change to a formula, guardrail, or response field **must**:
1. Update this spec first (the formula/table above).
2. Update the implementation to match.
3. Update or add the corresponding `pytest`/`node:test` case.
4. Update `test_plan.md`'s case table only if the test's *intent* changes (not just its status).

Do not let `user_manual.md` drift either — it is user-facing and must reflect the same truth.
