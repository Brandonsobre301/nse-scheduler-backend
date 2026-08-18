"""
efficiency_agent.py — NSE Scheduler Phase 2 Efficiency Inference Agent

Replaces the static assumedEfficiency input with a dynamically computed value
derived from historical project records stored in MongoDB Atlas.

Pipeline:
  1. Build a text description of the incoming project (same template as embedder.py)
  2. Embed it using all-MiniLM-L6-v2 (same model as embedder.py — vector space is consistent)
  3. Run Atlas $vectorSearch to retrieve the K most similar historical projects
  4. Compute a weighted average of their actualEfficiency values, where each
     weight is the cosine similarity score returned by Atlas
  5. Return the weighted efficiency + the matched projects as evidence

The agent is stateless — it loads the model once at module import and reuses it.
The SentenceTransformer model is cached locally after the first download.
"""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/nse_scheduler")
DB_NAME = "nse_scheduler"
COLLECTION = "historicalProjects"
INDEX_NAME = "historical_efficiency_index"
MODEL_NAME = "all-MiniLM-L6-v2"
DEFAULT_K = 5          # number of similar projects to retrieve
MIN_SCORE = 0.50       # discard matches below this cosine similarity threshold


# ---------------------------------------------------------------------------
# Module-level model — loaded once, reused across requests
# ---------------------------------------------------------------------------

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class EfficiencyInferenceResult:
    inferredEfficiency: float          # weighted average — use this as assumedEfficiency
    confidence: float                  # mean similarity score of matched projects (0-1)
    matchCount: int                    # number of projects that exceeded MIN_SCORE
    evidence: list[dict] = field(default_factory=list)  # matched projects for transparency
    warning: str | None = None         # set if matchCount is low or confidence is poor


# ---------------------------------------------------------------------------
# Text template — must match embedder.py exactly so vectors are comparable
# ---------------------------------------------------------------------------

def _build_query_text(
    project_type: str | None,
    budgeted_hrs: float | None,
    supervisor: str | None,
    job_name: str | None = None,
) -> str:
    parts = [
        project_type or "unknown type",
        f"{int(budgeted_hrs)} hours budgeted" if budgeted_hrs else "unknown budget",
        f"supervisor {supervisor}" if supervisor else "unknown supervisor",
    ]
    if job_name:
        parts.append(job_name)
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Core inference function
# ---------------------------------------------------------------------------

def infer_efficiency(
    project_type: str | None = None,
    budgeted_hrs: float | None = None,
    supervisor: str | None = None,
    job_name: str | None = None,
    k: int = DEFAULT_K,
) -> EfficiencyInferenceResult:
    """
    Infer assumedEfficiency for a new project from similar historical records.

    Args:
        project_type:  Type of project (e.g. "Office Tenant Improvement")
        budgeted_hrs:  Total man-hours budgeted (ce_budgetedHrs equivalent)
        supervisor:    Supervisor name — improves similarity matching
        job_name:      Optional job name for additional signal
        k:             Number of nearest neighbours to retrieve from Atlas

    Returns:
        EfficiencyInferenceResult with inferredEfficiency and supporting evidence
    """
    model = _get_model()

    # Build and embed the query text
    query_text = _build_query_text(project_type, budgeted_hrs, supervisor, job_name)
    query_vector = model.encode(query_text).tolist()

    # Query Atlas Vector Search
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION]

    pipeline = [
        {
            "$vectorSearch": {
                "index": INDEX_NAME,
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": k * 10,   # examine 10x candidates for better recall
                "limit": k,
            }
        },
        {
            "$project": {
                "_id": 0,
                "jobNumber": 1,
                "jobName": 1,
                "supervisor": 1,
                "projectType": 1,
                "ce_budgetedHrs": 1,
                "actualEfficiency": 1,
                "actualDurationWeeks": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]

    results = list(collection.aggregate(pipeline))
    client.close()

    # Filter out low-confidence matches and projects with no efficiency data
    valid = [
        r for r in results
        if r.get("score", 0) >= MIN_SCORE and r.get("actualEfficiency") is not None
    ]

    if not valid:
        # Fallback: no useful historical matches — return industry default
        return EfficiencyInferenceResult(
            inferredEfficiency=0.80,
            confidence=0.0,
            matchCount=0,
            warning=(
                "No similar historical projects found. "
                "Using industry default efficiency of 0.80. "
                "Provide assumedEfficiency manually for a more accurate estimate."
            ),
        )

    # Weighted average: weight each project's efficiency by its similarity score
    total_weight = sum(r["score"] for r in valid)
    weighted_efficiency = sum(
        r["actualEfficiency"] * r["score"] for r in valid
    ) / total_weight

    mean_confidence = total_weight / len(valid)

    # Build warning if confidence is low
    warning = None
    if len(valid) < 3:
        warning = (
            f"Only {len(valid)} similar project(s) found in history. "
            "Consider providing assumedEfficiency manually for higher confidence."
        )
    elif mean_confidence < 0.70:
        warning = (
            f"Similarity confidence is moderate ({mean_confidence:.2f}). "
            "The inferred efficiency may not reflect this project's specific conditions."
        )

    evidence = [
        {
            "jobNumber": r.get("jobNumber"),
            "jobName": r.get("jobName"),
            "supervisor": r.get("supervisor"),
            "projectType": r.get("projectType"),
            "actualEfficiency": r.get("actualEfficiency"),
            "similarityScore": round(r["score"], 4),
        }
        for r in valid
    ]

    return EfficiencyInferenceResult(
        inferredEfficiency=round(weighted_efficiency, 4),
        confidence=round(mean_confidence, 4),
        matchCount=len(valid),
        evidence=evidence,
        warning=warning,
    )
