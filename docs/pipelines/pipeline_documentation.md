PCO Data Pipeline: Engineering Architecture

## 1. Objective

This document outlines the complete architecture for an automated data pipeline to sync Proposed Change Order (PCO) data from the company's Deltek (DPS) system into the NSE Resource Scheduler's MongoDB database.

The primary goal is to automatically update a project's totalManHours in the Manpower Efficiency Calculator as new PCOs are approved, providing a real-time, accurate-as-possible "single source of truth" for project scope.

This design is modular, secure, and robust, with a special focus on idempotency and error handling to ensure data integrity.

## 2. System Architecture Overview

The pipeline will be built inside the existing Node.js (Express) backend. It will consist of three new, specialized modules that work together:

DeltekAPIService.ts (The "Connector"): A dedicated service responsible for all communication with the Deltek REST API. Its only job is to handle authentication and fetch data.

SyncService.ts (The "Brains"): This service contains the core business logic. It fetches data from the DeltekAPIService, transforms it, and applies the updates to our MongoDB database.

Scheduler (node-cron): A lightweight scheduler that runs the SyncService on an automated, nightly basis.

## 3. Key Design Principles (Addressing the Blind Spots)

This architecture is built on the following professional principles:

A. Idempotency (The "Run it Twice" Test)

This is the most critical design principle for this pipeline, as you've identified.

The Problem: If we simply fetch PCOs and add their hours (project.totalManHours += pco.manHourImpact), what happens if the script is run twice by accident, or if it fails midway and has to re-run? The project's hours would be added twice, corrupting the data.

The Solution: We must create a "memory" for the pipeline. We will create a new collection in MongoDB to log every PCO we process.

Before processing a new PCO from Deltek, the SyncService will first check: "Does a record for this pco_id already exist in our ProcessedPCOs collection?"

If YES, the script logs "Skipping already processed PCO..." and does nothing.

If NO, the script processes the PCO, updates the project's man-hours, and then saves a new record to the ProcessedPCOs collection.

This makes the pipeline idempotent, meaning it can be run 1,000 times on the same data and will only ever produce the correct result once.

B. Security (Secrets Management)

All sensitive credentials (DELTEK_CLIENT_ID, DELTEK_CLIENT_SECRET, DELTEK_API_URL) must be stored as environment variables in the .env file.

They will be loaded via process.env and never hardcoded into any .ts file.

C. Error Handling & Logging (The "Anti-Happy Path")

API-Level: The DeltekAPIService must have try...catch blocks to handle network failures or authentication errors (e.g., if the Deltek API is down).

Job-Level: The SyncService will be wrapped in a try...catch block. If the API fails, the entire job will log the error and stop, to be retried on the next scheduled run.

Item-Level: The loop inside the SyncService will also have a try...catch block. This is crucial: if a single PCO fails (e.g., its project_number doesn't exist in our database), the script will log the error for that single item and continue to the next PCO. This prevents one bad piece of data from stopping the entire sync.

4. Data Flow (Step-by-Step)

This is the exact sequence of events for a nightly sync:

[Scheduler] At 2:00 AM, node-cron calls the SyncService.runPCOSync() function.

[SyncService] Logs "PCO Sync Job Started."

[SyncService] Calls const pcos = await DeltekAPIService.getNewPCOs().

[DeltekAPIService]
a. Calls its internal getAccessToken() function to get a fresh token from Deltek's /token endpoint.
b. Makes a GET request to the Deltek PCO endpoint (e.g., /projectplan/details) using the token.
c. Returns the array of PCO objects (as JSON) to the SyncService.

[SyncService]
a. Receives the pcos array.
b. Begins a loop: for (const pco of pcos) { ... }
c. [IDEMPOTENCY CHECK] Calls const alreadyProcessed = await ProcessedPCO.findOne({ pcoId: pco.id });
d. If alreadyProcessed, logs "Skipping..." and continues to the next PCO.
e. If not processed, it finds the project: const project = await Project.findOne({ projectNumber: pco.project_number });
f. If !project, logs a warning: "Could not find matching project for PCO..."
g. If project is found, it updates the hours: project.totalManHours += pco.man_hour_impact;
h. It saves both updates in a database transaction (to ensure they either both succeed or both fail):
i. await project.save();
ii. await ProcessedPCO.create({ pcoId: pco.id, ... });
i. Logs success for that item.

[SyncService] After the loop finishes, logs "PCO Sync Job Finished."

## 5. Required Database Schema Changes

To support this pipeline, our Mongoose models must be updated.

1. Project.ts (Modify Existing Model)

We must add a new field that will be the "key" to match against Deltek data.

// Login_server/models/Project.ts
// ... other fields
projectNumber: {
  type: String,
  required: true,
  unique: true, // This is the unique ID from Deltek/Accounting
  index: true
},
totalManHours: {
  type: Number,
  default: 0
},
// ...


2. ProcessedPCO.ts (Create New Model)

This new collection is the "memory" for our idempotency check.

// Login_server/models/ProcessedPCO.ts
import mongoose, { Document, Schema } from 'mongoose';

export interface IProcessedPCO extends Document {
  pcoId: string; // The unique ID from Deltek
  projectNumber: string;
  manHourImpact: number;
  processedAt: Date;
}

const ProcessedPCOSchema: Schema = new Schema({
  pcoId: { type: String, required: true, unique: true, index: true },
  projectNumber: { type: String, required: true },
  manHourImpact: { type: Number, required: true },
  processedAt: { type: Date, default: Date.now }
});

export default mongoose.model<IProcessedPCO>('ProcessedPCO', ProcessedPCOSchema);


 ## 6. Future Generalization

This architecture is built to be "general." By separating the DeltekAPIService from the SyncService, we can easily add new data sources in the future without changing our core business logic.

For example, if another department wants to send data via a CSV file, we would simply:

Create a new CsvReaderService.ts.

Have it read the CSV and transform it into the same standard PCO object format that the DeltekAPIService returns.

The SyncService wouldn't change at all. It would just call CsvReaderService.getNewPCOs() and process the data exactly as before.