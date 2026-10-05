# Estimation Engine — User Manual

## 1. What Is the Estimation Engine?

The Estimation Engine ("prediction feature") answers two questions project managers and
schedulers ask constantly:

1. **"If I put N electricians on this job, how many weeks will it take?"** (Mode 1 — Calculate Duration)
2. **"If I have to be done in N weeks, how many electricians do I need?"** (Mode 2 — Calculate Manpower)

Both calculations depend on a labor **efficiency** factor — how productively a crew actually
performs versus the ideal, 100%-efficient baseline. You can supply this number yourself, or
let the engine infer it automatically from similar historical NSE projects using AI
(vector similarity search over 72+ completed jobs).

The engine is exposed to the rest of the application as a single endpoint:

```
POST /api/v1/estimate
```

reached through the Node.js API Gateway (`http://localhost:5000/api/v1/estimate`). You never
call the Python AI service directly — it isn't reachable outside the Docker network.

## 2. Key Concepts

| Term | Meaning |
|---|---|
| **Man-Hours (H)** | Total labor hours bid/budgeted for the job. |
| **Manpower (MP)** | Number of workers (crew size) assigned to the job. |
| **Efficiency (E)** | Productivity factor. `1.0` = crew performs exactly at the estimated rate. `0.85` = crew is 15% less productive than ideal. Values above `1.0` (up to `2.0`) are valid — some crews finish under budget. |
| **Duration (weeks)** | How many 40-hour work-weeks the job will take. |
| **Target Duration (T)** | A hard deadline, expressed in weeks, that you need the crew to hit. |

## 3. The Two Calculation Modes

### Mode 1 — Calculate Duration

Use this when your crew size is fixed and you need to know the finish date.

**You provide:** `totalManHours`, `desiredManpower`, and (optionally) `assumedEfficiency`.

**You get back:**
- `realisticDurationWeeks` — how long the job will actually take
- `totalExpendedHours` — total labor hours that will be burned, efficiency loss included

**Formula:** `RD = (H / 40 / MP) / E`, `EH = RD × MP × 40`

### Mode 2 — Calculate Manpower

Use this when you have a fixed deadline and need to know how big a crew to staff.

**You provide:** `totalManHours`, `targetDurationWeeks`, and (optionally) `assumedEfficiency`.

**You get back:**
- `recommendedManpower` — the minimum crew size (always rounded **up**, never down, so the
  deadline is never missed)

**Formula:** `RM = ceil( (H / 40) / (T × E) )`

## 4. Letting the AI Infer Efficiency (Optional)

If you don't know what efficiency to assume, simply omit `assumedEfficiency` from your
request. The engine will:

1. Build a short text description of your project from `projectType`, `totalManHours`,
   `supervisor`, and `jobName`.
2. Search MongoDB Atlas for the 5 most similar historical projects (by semantic meaning,
   not exact keyword match).
3. Average their actual recorded efficiencies, weighted by how similar each match is.
4. Return that number as `calculatedEfficiency`, along with the evidence used.

To get the most accurate inference, provide as much of this optional context as you can:

| Field | Why it helps |
|---|---|
| `projectType` | e.g. "Office Tenant Improvement" — the single biggest driver of similarity |
| `supervisor` | Different supervisors run crews at different real-world efficiencies |
| `jobName` | Minor additional signal |

### Understanding `efficiencySource` in the response

| Value | Meaning |
|---|---|
| `provided` | You supplied `assumedEfficiency` yourself — no AI involved. |
| `agent_inferred` | The AI found at least one similar historical project above the confidence threshold and used it. |
| `fallback_default` | The AI found **no** sufficiently similar historical projects, so it fell back to an industry-standard default of `0.80`. Treat this result with caution. |

### Understanding the confidence fields

| Field | Meaning |
|---|---|
| `inferenceMatchCount` | How many historical projects were similar enough (similarity score ≥ 0.50) to be used. |
| `inferenceConfidence` | Average similarity score (0–1) of the matched projects. Higher is better. |
| `inferenceEvidence` | The actual historical jobs used, with their job number, name, supervisor, and recorded efficiency — for transparency/audit. |
| `warnings` | Plain-language callouts, e.g. "Only 1 similar project found" or "Similarity confidence is moderate". Always read this list before trusting the result. |

## 5. Making a Request

All requests must include a valid JWT in the `Authorization` header, exactly like every other
authenticated route in the app (`Authorization: Bearer <token>`).

### Example — Mode 1, manual efficiency

```bash
curl -X POST http://localhost:5000/api/v1/estimate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_jwt_token>" \
  -d '{
        "projectId": "PROJ-1042",
        "calculationMode": "duration",
        "inputs": {
          "totalManHours": 4800,
          "desiredManpower": 6,
          "assumedEfficiency": 0.85
        }
      }'
```

### Example — Mode 2, AI-inferred efficiency

```bash
curl -X POST http://localhost:5000/api/v1/estimate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_jwt_token>" \
  -d '{
        "projectId": "PROJ-1042",
        "calculationMode": "manpower",
        "inputs": {
          "totalManHours": 4800,
          "targetDurationWeeks": 20,
          "projectType": "Office Tenant Improvement",
          "supervisor": "Joe Lawhorn"
        }
      }'
```

## 6. Reading the Response

```json
{
  "status": "success",
  "projectId": "PROJ-1042",
  "calculationMode": "manpower",
  "outputs": {
    "realisticDurationWeeks": null,
    "totalExpendedHours": null,
    "recommendedManpower": 8,
    "calculatedEfficiency": 0.79,
    "efficiencySource": "agent_inferred",
    "warnings": [],
    "inferenceMatchCount": 5,
    "inferenceConfidence": 0.81,
    "inferenceEvidence": [ { "jobNumber": "2144", "jobName": "...", "actualEfficiency": 0.78, "similarityScore": 0.83 } ]
  }
}
```

Fields that don't apply to the mode you requested are always returned as `null` (not omitted),
so client code can rely on a stable shape.

## 7. Error Messages

| Situation | HTTP Status | What it means |
|---|---|---|
| `totalManHours`, `desiredManpower`, `targetDurationWeeks` ≤ 0 | 400 | A numeric input that must be positive was zero or negative. |
| `assumedEfficiency` ≤ 0 or > 2.0 | 400 | Efficiency must be in `(0, 2.0]`. |
| `desiredManpower` missing while `calculationMode` is `"duration"` | 400 | That field is required for Mode 1. |
| `targetDurationWeeks` missing while `calculationMode` is `"manpower"` | 400 | That field is required for Mode 2. |
| Malformed JSON, wrong types, invalid `calculationMode` value | 422 | Request failed schema validation before it even reached the calculation logic. |
| Missing/invalid JWT | 401 | Returned by Express before the request ever reaches the AI service. |
| AI service unreachable | 503 | The FastAPI container is down or unreachable on the Docker network; retry later. |

## 8. Who Can Use This Feature?

Any authenticated user (any RBAC role) can call `/api/v1/estimate` today — there is no
role-based restriction on this route. If your organization needs to restrict estimation to
`manager`/`admin` roles, that would need to be added to `estimateRoutes.ts`.

## 9. Frequently Asked Questions

**Q: Can I use both a manual efficiency and get AI evidence back?**
No — if you supply `assumedEfficiency`, the AI inference step is skipped entirely and the
`inference*` fields are returned as `null`.

**Q: Why did I get `fallback_default` instead of a real inference?**
No historical project reached the minimum similarity threshold (0.50). This usually means the
project type or scale is unlike anything in the historical dataset. Supply `assumedEfficiency`
manually for a more trustworthy result.

**Q: Can efficiency be greater than 1.0?**
Yes. `E > 1.0` means the crew is outperforming the estimate. The valid range is `(0, 2.0]`.

**Q: Is `recommendedManpower` ever rounded down?**
Never. It always uses `ceil()` so the crew size is sufficient to hit the deadline; this can
mean the job finishes slightly ahead of schedule.
