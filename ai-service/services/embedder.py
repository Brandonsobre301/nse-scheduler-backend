"""
embedder.py — NSE Scheduler Vector Embedding Service

Generates 384-dimensional sentence embeddings for each historicalProjects
document and stores them back to MongoDB Atlas. The Atlas Vector Search index
`historical_efficiency_index` queries the `embedding` field populated here.

Model: all-MiniLM-L6-v2 (sentence-transformers)
  - 384 dimensions — matches the Atlas index numDimensions exactly
  - ~90MB one-time download, cached locally after first run
  - No API key or external service required

Usage (standalone — run once after ingest):
    python services/embedder.py

Usage (incremental — safe to re-run, skips already-embedded docs):
    python services/embedder.py --force   # re-embeds all documents
"""

import argparse
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from sentence_transformers import SentenceTransformer

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/nse_scheduler")
DB_NAME = "nse_scheduler"
COLLECTION = "historicalProjects"
MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 32


def build_embed_text(doc: dict) -> str:
    project_type = doc.get("projectType") or "unknown type"
    supervisor = doc.get("supervisor") or "unknown supervisor"
    budgeted_hrs = doc.get("ce_budgetedHrs")
    efficiency = doc.get("actualEfficiency")
    duration = doc.get("actualDurationWeeks")
    job_name = doc.get("jobName") or ""

    parts = [
        f"{project_type}",
        f"{int(budgeted_hrs)} hours budgeted" if budgeted_hrs else "unknown budget",
        f"supervisor {supervisor}",
        f"actual efficiency {efficiency:.2f}" if efficiency else "unknown efficiency",
        f"{duration:.1f} weeks duration" if duration else "unknown duration",
    ]
    if job_name:
        parts.append(job_name)

    return ", ".join(parts)


def run(force: bool = False) -> None:
    print(f"[1/4] Loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)
    print(f"      Embedding dimensions: {model.get_sentence_embedding_dimension()}")

    print("[2/4] Connecting to MongoDB...")
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION]

    query = {} if force else {"embedding": {"$exists": False}}
    docs = list(collection.find(query, {
        "_id": 1, "jobNumber": 1, "jobName": 1, "projectType": 1,
        "supervisor": 1, "ce_budgetedHrs": 1, "actualEfficiency": 1,
        "actualDurationWeeks": 1,
    }))

    if not docs:
        print("      No documents need embedding — all up to date.")
        client.close()
        return

    print(f"[3/4] Embedding {len(docs)} documents in batches of {BATCH_SIZE}...")

    ops = []
    total_batches = (len(docs) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(total_batches):
        batch = docs[batch_idx * BATCH_SIZE : (batch_idx + 1) * BATCH_SIZE]
        texts = [build_embed_text(doc) for doc in batch]
        embeddings = model.encode(texts, show_progress_bar=False)

        for doc, embedding in zip(batch, embeddings):
            ops.append(UpdateOne(
                {"_id": doc["_id"]},
                {"$set": {
                    "embedding": embedding.tolist(),
                    "embeddedAt": datetime.now(timezone.utc),
                    "embedModel": MODEL_NAME,
                }},
            ))

        print(f"      Batch {batch_idx + 1}/{total_batches} complete "
              f"({min((batch_idx + 1) * BATCH_SIZE, len(docs))}/{len(docs)} docs)")

    print("[4/4] Writing embeddings to MongoDB...")
    result = collection.bulk_write(ops)
    print(f"      Modified {result.modified_count} documents")

    client.close()
    print("\n✅ Embedding complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="Re-embed all documents, even those already embedded")
    args = parser.parse_args()
    run(force=args.force)