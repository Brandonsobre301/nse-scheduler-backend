# NSE Scheduler — Backend Workspace Instructions

You are working on the **NSE Scheduler**, an enterprise workforce management system for electrical construction. Follow these rules on every interaction.

## Architecture (CRITICAL — enforce without exception)

```
React Frontend (:3000)
    ↓ JWT Bearer token
Node.js / Express API Gateway (:5000)        ← public entry point
    ↓ internal Docker network (app-net)
Python 3.12 / FastAPI Reasoning Engine (:8000, NEVER exposed publicly)
    ↓
MongoDB Atlas (nse_scheduler db)
    ├── projects              — live operational data
    └── historicalProjects    — 72 real records + 384-dim embeddings
```

**The frontend MUST NEVER call the FastAPI service directly.** Every client request routes through Express (`/api/v1/estimate`), which proxies across `app-net` to `http://ai-service:8000`. Any code that violates this boundary is a bug.

When adding or modifying an endpoint, always update BOTH:
1. `ai-service/routers/<router>.py` — FastAPI route
2. `routes/estimateRoutes.ts` — Express proxy route

## Estimation Math (enforce exactly)

### Mode 1: Calculate Duration
- `RD = H / (40 × MP × E)`
- `EH = H / E`

### Mode 2: Calculate Manpower
- `RM = ceil( H / (40 × T × E) )`

Variables: `H` = man-hours, `MP` = crew size, `E` = efficiency `(0, 2.0]`, `T` = target weeks.
Values of `E > 1.0` are valid — real crews finish under-budget (historical data confirms).
Always `ceil()` manpower — rounding down misses the deadline.

## Guardrails (enforced in `estimation_engine.py`)
- `E ≤ 0`, `MP ≤ 0`, `T ≤ 0`, `H ≤ 0` → `ValueError` → HTTP 400
- `E > 2.0` → `ValueError` with explicit message
- Pydantic schema violations → HTTP 422

## Phase 2: AI Efficiency Inference (implemented, active)
When `assumedEfficiency` is omitted: embed query text → Atlas `$vectorSearch` → weighted average of matched `actualEfficiency` values → `efficiencySource: "agent_inferred"`. Fallback to `0.80` if no matches above `MIN_SCORE = 0.50`.

## Key File Map

| Concern | File |
|---|---|
| Estimation math | `ai-service/services/estimation_engine.py` |
| AI inference | `ai-service/services/efficiency_agent.py` |
| Vector embeddings | `ai-service/services/embedder.py` |
| ETL pipeline | `ai-service/scripts/ingest.py` |
| FastAPI router | `ai-service/routers/estimate.py` |
| Pydantic schemas | `ai-service/models/estimation.py` |
| Express proxy | `routes/estimateRoutes.ts` |
| Auth middleware | `middleware/auth.ts` |

## Coding Standards
- Fail early: never calculate with invalid inputs; return structured JSON with `warnings[]`
- No hardcoded data in production code: query MongoDB directly
- All Python: Pydantic v2 strictly typed. All TypeScript: strict mode.
- `sentence-transformers` is NOT in the Docker image — Phase 2 requires model cache mounted or baked in.
- Before running Python scripts in PowerShell: `Remove-Item Env:MONGODB_URI` if previously set (load_dotenv does not override existing env vars).