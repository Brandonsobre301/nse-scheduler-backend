# Estimation Engine — Test Plan

> **See [spec.md](./spec.md) for the authoritative formulas, data contracts, and guardrail
> status codes.** This document is the test strategy/case catalogue; it must not contradict
> spec.md. As of the automated suite below, several original case expectations here (marked
> ~~struck through~~) were found to be incorrect against the real implementation and corrected
> in spec.md §4 — keep that file, not this one, as the source of truth for expected status codes.

## 1. Purpose & Scope

This document defines the test strategy for the **Estimation Engine / prediction feature**:
the deterministic duration/manpower calculators (Phase 1) and the AI efficiency inference
agent (Phase 2), across all three layers of the stack:

- `ai-service/services/estimation_engine.py` — pure calculation logic
- `ai-service/services/efficiency_agent.py` — Atlas Vector Search inference
- `ai-service/routers/estimate.py` + `ai-service/models/estimation.py` — FastAPI contract
- `routes/estimateRoutes.ts` — Express authenticated proxy

Out of scope: PCO data pipeline (`docs/pipelines/`), general project CRUD, and frontend UI
(tracked in the frontend repo).

## 2. Test Objectives

1. Verify both calculation modes produce mathematically correct results per the spec formulas.
2. Verify all guardrails reject invalid input with the correct HTTP status and message.
3. Verify the AI efficiency agent returns correct, well-labeled results across all confidence
   scenarios (high confidence, low match count, no matches).
4. Verify the Express ↔ FastAPI boundary is secure and resilient (auth enforced, network
   isolation held, service-down handled gracefully).
5. Verify response schema stability (`null` fields present, not omitted) for client safety.

## 3. Test Environment

| Component | Setup |
|---|---|
| ai-service | Local Python 3.12 venv or `docker-compose up ai-service`, port 8000 (internal only) |
| backend | `npm run dev`, port 5000 |
| MongoDB | Atlas cluster (required for `$vectorSearch`) or local Mongo for non-inference tests |
| historicalProjects | Seeded via `ai-service/scripts/ingest.py` from `data/job_hours.csv`, then embedded via `ai-service/services/embedder.py` |
| Atlas Search Index | `historical_efficiency_index` on `embedding` field, 384 dimensions, must exist before inference tests |
| Auth | Valid JWT obtained via existing `/api/v1/auth/login`-style flow, using `JWT_SECRET` from `.env` |

Environment variables required: `MONGODB_URI` (Atlas), `MONGO_URI` (app db), `JWT_SECRET`,
`AI_SERVICE_URL`. Note: unset any pre-existing `MONGODB_URI` shell variable before running
ingestion/embedding scripts locally, since `load_dotenv()` will not override it.

## 4. Test Levels

| Level | Tooling | Target |
|---|---|---|
| Unit — engine math | `pytest` against `estimation_engine.py` functions directly (no FastAPI needed) | `calculate_duration`, `calculate_manpower`, validators |
| Unit — inference agent | `pytest` with a test/mocked Atlas collection or a seeded test DB | `infer_efficiency`, `_build_query_text` |
| Integration — API contract | FastAPI `TestClient` against `main.py` | `POST /api/v1/estimate` end to end |
| Integration — proxy | `supertest`/`jest` (or manual `curl`) against Express with `ai-service` running | `estimateRoutes.ts` |
| Manual / Exploratory | Postman / curl per the User Manual examples | Full stack via `:5000` |
| Security | Manual + review | Auth boundary, network isolation, input validation |

`test_agent.py` currently exists as an ad-hoc manual smoke script for the inference agent;
it is not a substitute for the automated cases below and should eventually be migrated into
a proper `pytest` suite (e.g. `ai-service/tests/`).

## 5. Entry / Exit Criteria

**Entry:** ai-service builds and passes `/health`; historicalProjects seeded and embedded;
Atlas vector index reports `READY`.

**Exit:** All P1 test cases pass; no open Sev-1/Sev-2 defects; guardrail cases return the
exact status codes specified in the spec; schema fields verified stable across both modes.

## 6. Detailed Test Cases

### 6.1 Mode 1 — Calculate Duration (engine math)

| ID | Description | Input | Expected | Priority |
|---|---|---|---|---|
| TC-D01 | Valid duration calc, E = 1.0 | H=4800, MP=6, E=1.0 | RD=20.0 weeks, EH=4800 | P1 |
| TC-D02 | Valid duration calc, E < 1.0 (inefficient crew) | H=4800, MP=6, E=0.8 | RD=25.0 weeks, EH=6000 | P1 |
| TC-D03 | Valid duration calc, E > 1.0 (over-performing crew) | H=4800, MP=6, E=1.2 | RD≈16.67 weeks, ~~EH=4800~~ **EH=4000.0** (corrected — EH=H/E) | P1 |
| TC-D04 | Result precision | any valid input | `realisticDurationWeeks`/`totalExpendedHours` rounded to 2 decimals | P2 |

### 6.2 Mode 2 — Calculate Manpower (engine math)

| ID | Description | Input | Expected | Priority |
|---|---|---|---|---|
| TC-M01 | Manpower calc lands on whole number | H=4800, T=20, E=1.0 | RM=6, exactManpower=6.0 | P1 |
| TC-M02 | Manpower calc requires ceiling | H=4800, T=20, E=0.9 | exactManpower≈6.67 → RM=7 (never 6) | P1 |
| TC-M03 | exactManpower precision | any fractional case | rounded to 4 decimals | P2 |

### 6.3 Guardrails / Validation

| ID | Description | Input | Expected | Priority |
|---|---|---|---|---|
| TC-G01 | `totalManHours` = 0 | H=0 | ~~400~~ **422** (Pydantic `gt=0`) | P1 |
| TC-G02 | `totalManHours` negative | H=-100 | ~~400~~ **422** | P1 |
| TC-G03 | `desiredManpower` = 0 (duration mode) | MP=0 | ~~400~~ **422** | P1 |
| TC-G04 | `targetDurationWeeks` = 0 (manpower mode) | T=0 | ~~400~~ **422** | P1 |
| TC-G05 | `assumedEfficiency` = 0 | E=0 | ~~400~~ **422** (Pydantic `gt=0`) | P1 |
| TC-G06 | `assumedEfficiency` > 2.0 | E=2.5 | ~~400~~ **422** (Pydantic `le=2.0` — caught before the engine's own guardrail ever runs) | P1 |
| TC-G07 | `assumedEfficiency` exactly 2.0 (boundary) | E=2.0 | Accepted (inclusive upper bound) | P2 |
| TC-G08 | `desiredManpower` omitted, mode="duration" | — | ~~400~~ **422** (`model_validator`'s `ValueError` is wrapped into a Pydantic `ValidationError`) | P1 |
| TC-G09 | `targetDurationWeeks` omitted, mode="manpower" | — | ~~400~~ **422** (same reason as TC-G08) | P1 |
| TC-G10 | `calculationMode` invalid value (e.g. "speed") | — | 422 (Pydantic Literal violation) | P1 |
| TC-G11 | `projectId` missing/empty | — | 422 | P2 |
| TC-G12 | Wrong type (e.g. `totalManHours` as string "abc") | — | 422 | P2 |

### 6.4 AI Efficiency Inference

| ID | Description | Setup | Expected | Priority |
|---|---|---|---|---|
| TC-A01 | `assumedEfficiency` omitted, strong historical matches exist | seeded DB with ≥5 similar projects | `efficiencySource="agent_inferred"`, `inferenceMatchCount≥3`, no warning | P1 |
| TC-A02 | No historical matches above `MIN_SCORE` (0.50) | query for an unrepresented project type | `efficiencySource="fallback_default"`, `calculatedEfficiency=0.80`, warning present | P1 |
| TC-A03 | 1–2 matches only | sparse historical data scenario | `agent_inferred` but warning: "Only N similar project(s) found..." | P2 |
| TC-A04 | Matches found but moderate confidence (<0.70 mean score) | crafted query | warning: "Similarity confidence is moderate..." | P2 |
| TC-A05 | Weighted average correctness | 2 known matches with known scores/efficiencies | Manually verify weighted average formula output | P1 |
| TC-A06 | `assumedEfficiency` provided — inference skipped entirely | E supplied | `efficiencySource="provided"`, all `inference*` fields `null` | P1 |
| TC-A07 | Evidence list contents | any inferred case | `inferenceEvidence` contains jobNumber, jobName, supervisor, projectType, actualEfficiency, similarityScore for each match | P2 |
| TC-A08 | Query text consistency | — | `_build_query_text` (agent) and `build_embed_text` (embedder) produce comparable semantic content so vector space matches | P2 |

### 6.5 Response Schema Stability

| ID | Description | Expected | Priority |
|---|---|---|---|
| TC-S01 | Mode "duration" response | `recommendedManpower` explicitly `null`, not omitted | P1 |
| TC-S02 | Mode "manpower" response | `realisticDurationWeeks`/`totalExpendedHours` explicitly `null` | P1 |
| TC-S03 | `warnings` always an array (never `null`) | empty array when no warnings | P2 |

### 6.6 Express Proxy & Security Boundary

| ID | Description | Expected | Priority |
|---|---|---|---|
| TC-P01 | Request without `Authorization` header | 401 from Express; ai-service never invoked | P1 |
| TC-P02 | Request with invalid/expired JWT | 401 from Express | P1 |
| TC-P03 | Valid JWT, ai-service container stopped | 503 with "Estimation service is unavailable" message | P1 |
| TC-P04 | Valid JWT, ai-service healthy | Express returns the exact status/body from FastAPI (200/400/422) unmodified | P1 |
| TC-P05 | Attempt to reach `ai-service:8000` directly from outside the Docker network | Connection refused/unreachable — port 8000 is not published to host | P1 |
| TC-P06 | CORS: request from an unlisted origin directly to ai-service | Blocked by FastAPI CORS middleware (defense in depth) | P2 |

### 6.7 Performance / Load (lightweight)

| ID | Description | Expected | Priority |
|---|---|---|---|
| TC-L01 | Cold start — first inference request loads `SentenceTransformer` model | Completes within acceptable startup latency; subsequent requests reuse cached module-level model | P2 |
| TC-L02 | Concurrent requests (e.g. 10 parallel `/estimate` calls) | All complete successfully; no shared-state corruption from module-level model | P3 |

## 7. Regression Suite Recommendation — IMPLEMENTED

Automated as of this revision:
- `ai-service/tests/test_estimation_engine.py` — sections 6.1–6.3
- `ai-service/tests/test_efficiency_agent.py` — section 6.4 (mocked `pymongo`/model via `conftest.py`)
- `ai-service/tests/test_estimate_router.py` — sections 6.3–6.5, using FastAPI `TestClient`
- `routes/estimateRoutes.test.ts` — section 6.6, using Node's built-in test runner

Run with `pytest` (from `ai-service/`, after `pip install -r requirements-dev.txt`) and
`npm test` (from repo root). Not yet in CI — add a workflow that runs both on every PR
touching `ai-service/` or `routes/estimateRoutes.ts`. See [spec.md](./spec.md) §7 for the
full requirement-to-test traceability matrix.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Atlas Vector Search index not built/stale in test env | Verify index status via Atlas UI before running section 6.4 |
| `sentence-transformers` not baked into Docker image | Confirm model cache is mounted/baked before running inference tests in containers |
| Historical dataset changes (re-ingest) shift inference results | Pin/snapshot test dataset for TC-A05 exact-value assertions |

## 9. Sign-off

| Role | Responsibility |
|---|---|
| Backend engineer | Executes 6.1–6.3, 6.5, 6.6 |
| AI/ML engineer | Executes 6.4, owns TC-A05 weighted-average verification |
| QA / reviewer | Executes manual exploratory pass per User Manual §5, approves exit criteria |
