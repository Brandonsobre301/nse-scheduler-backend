PCO Data Pipeline: CSV Prototype Architecture

## 1. Objective

This document outlines the architecture for an initial prototype pipeline to sync PCO data from a CSV file into the NSE Resource Scheduler's MongoDB database.

The goal is to provide a simple, reliable way to test the data integration and demonstrate the value of the PCO-to-Calculator feature while waiting for full API access. This script is designed to be run manually (or on a simple schedule) and serves as the logical foundation for the final API-based pipeline.

## 2. System Architecture Overview

This pipeline will be a standalone Python script, separate from your Node.js backend. This is the industry-standard approach for this kind of task, as it's simple, robust, and perfect for file manipulation.

Data Source: A .csv file (e.g., pcos_export.csv) placed in a known location (e.g., a shared drive or a folder within the script's directory).

The Engine (sync_pcos.py): A Python script that uses pandas to read the CSV and pymongo to communicate with your MongoDB.

Data Destination: Your existing MongoDB database.

## 3. Key Design Principles (The Same Rules Apply)

Even though this is a prototype, we will follow the same professional principles as the API plan. This ensures the logic is sound and reusable.

A. Idempotency (The "Run it Twice" Test)

The Problem: The daily CSV export from Deltek might contain all PCOs, not just new ones. If we simply add hours, running the script on Tuesday would re-add all of Monday's hours.

The Solution: We will use the exact same "memory" collection as the API plan.

The CSV file must contain a unique ID for each PCO (e.g., pco_id or change_order_number).

Before processing a row, the script will check: "Does a record for this pco_id already exist in our ProcessedPCOs collection?"

If YES, it skips the row.

If NO, it processes the row, updates the project, and saves a new record to ProcessedPCOs.

B. Security (Secrets Management)

The MongoDB connection string must be stored in a .env file alongside the script. It will never be hardcoded.

C. Error Handling & Logging (The "Anti-Happy Path")

The script will wrap the processing of each row in a try...except block.

This is critical for CSVs, which are notoriously "dirty." If one row has a typo (e.g., "abc" in the man_hour_impact column), the script will log the error for that row and continue to the next, ensuring one bad entry doesn't stop the entire process.

## 4. Required Setup & Data Contract

This is your "to-do" list to get this prototype working.

1. Set Up Your Python Environment:

Install Python on your machine.

In your terminal, install the required libraries:

pip install pandas pymongo python-dotenv


2. Define the Data Contract (The CSV File):

This is what you need to ask your admin to provide in the sample CSV file. It must have these three columns:

pco_id: A unique identifier for the change order.

project_number: The project ID that matches the projectNumber in your MongoDB.

man_hour_impact: The number of hours to add (e.g., 200) or subtract (e.g., -50).

3. Prepare the Database:

You must implement the exact same schema changes from the API architecture plan. This is perfect because this "trial" builds the permanent foundation.

Modify Project.ts: Add the projectNumber field.

Create ProcessedPCO.ts: Create the new model to log processed PCOs.

## 5. Data Flow (Step-by-Step Script Logic)

This is the logic you will build inside your sync_pcos.py script.

[Script] RUN python sync_pcos.py.

[Script] Script loads environment variables from .env (especially MONGO_URI).

[Script] Console Logs "Starting PCO-CSV sync..."

[Script] Connects to your MongoDB database using pymongo.

[Script (Extract)] Reads the CSV file (e.g., pcos_export.csv) into a pandas DataFrame.

[Script (Transform)]

Logs how many rows were found (e.g., "Found 50 PCOs in CSV.").

Cleans the data: ensures man_hour_impact is numeric, drops any rows with missing data.

[Script (Load)]

Begins a loop: for index, row in df.iterrows(): { ... }

Inside a try...except block:

[IDEMPOTENCY CHECK] Checks the ProcessedPCOs collection for row['pco_id'].

If alreadyProcessed, logs "Skipping..." and continues.

If not processed, finds the project: project = db.projects.find_one({ projectNumber: row['project_number'] })

If !project, logs a warning: "Could not find matching project..."

If project is found, it calculates the new hours: new_hours = project['totalManHours'] + row['man_hour_impact']

It updates the project in the database: db.projects.update_one(...)

It then inserts the log record: db.processedpcos.insert_one(...)

Logs success for that item.

[Script] After the loop finishes, logs "PCO-CSV Sync Job Finished."

This prototype is a powerful and practical first step. The core logic you build in this Python script is 99% identical to the logic you'll eventually build in your SyncService.ts, making this an incredibly valuable and reusable "trial run."