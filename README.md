NSE Resource Scheduler

A centralized operations dashboard and resource planning tool designed to bridge the gap between office scheduling and field execution.

Features

Authentication: Secure login and registration with Role-Based Access Control (RBAC).

Project Management: Full CRUD operations for active job sites.

Resource Calculators: Algorithms to calculate required manpower vs. project duration.

AI Estimation Engine: A dedicated Python/FastAPI microservice that calculates project duration or required manpower, and — when an efficiency value isn't supplied — infers a realistic efficiency from 72+ historical projects using MongoDB Atlas Vector Search. See the [Estimation Engine User Manual](docs/estimation-engine/user_manual.md) and [Test Plan](docs/estimation-engine/test_plan.md).

Live Operations Dashboard: Real-time matrix of active phases, manpower distribution, and site status (Green/Yellow/Red indicators).

Estimation Engine Architecture

```
React Frontend (:3000)
    ↓ JWT Bearer token
Node.js / Express API Gateway (:5000)        ← public entry point, POST /api/v1/estimate
    ↓ internal Docker network (app-net)
Python 3.12 / FastAPI Reasoning Engine (:8000, never exposed publicly)
    ↓
MongoDB Atlas (nse_scheduler db)
    ├── projects              — live operational data
    └── historicalProjects    — historical job-hours records + 384-dim embeddings
```

The frontend never calls the FastAPI service directly — every request is authenticated by Express and proxied internally. See [routes/estimateRoutes.ts](routes/estimateRoutes.ts) and [ai-service/routers/estimate.py](ai-service/routers/estimate.py).

Prerequisites

To run this application on your local machine, you will need:

Node.js (v20 or higher)

Python 3.12 (for the ai-service estimation microservice — only required if you're running the AI service outside Docker)

MongoDB (Running locally or a MongoDB Atlas URI — Atlas is required for the estimation engine's AI efficiency inference, since it uses Atlas Vector Search)

Installation & Setup

1. Clone the Repository

git clone <your-github-repo-url>
cd <your-repo-name>


2. Environment Variables

You need to set up your local environment variables. Create a .env file in the root of your backend folder and add the following:

PORT=5000
MONGO_URI=your_mongodb_connection_string_here
JWT_SECRET=your_super_secret_jwt_key

# Estimation Engine (ai-service)
MONGODB_URI=your_mongodb_atlas_connection_string_here
AI_SERVICE_URL=http://ai-service:8000
AI_SERVICE_API_KEY=a_shared_random_secret_used_by_both_services


3. Install Dependencies

You will need to install the Node modules for both the frontend and the backend.

For the Backend:

cd Login_server
npm install


For the Frontend:

cd nse-scheduler-frontend
npm install


Windows Quick Start Script

If you are developing on a Windows machine, you can use the following batch script to automatically open VS Code and start both the frontend and backend servers simultaneously.

Open Notepad.

Paste the following code:

@echo off
set "backendPath=C:\Users\brand\Desktop\NSE WEB app\Login_server"
set "frontendPath=C:\Users\brand\Desktop\NSE WEB app\nse-scheduler-frontend"

:: --- SCRIPT LOGIC ---

:: Open backend in VS Code
start "" "C:\Users\brand\AppData\Local\Programs\Microsoft VS Code\Code.exe" "%backendPath%"
:: Run backend server
start "" cmd /k "cd /d %backendPath% && npx ts-node server.ts"

:: Open frontend in VS Code
start "" "C:\Users\brand\AppData\Local\Programs\Microsoft VS Code\Code.exe" "%frontendPath%"
:: Run frontend server
start "" cmd /k "cd /d %frontendPath% && npm start"


Save the file to your Desktop as start_app.bat.

Double-click the file to launch your entire development environment!

Manual Running

To run the app manually, you need to start both the backend server and the frontend client in two separate terminal windows.

Terminal 1 (Backend):

cd Login_server
npm run dev
# The server should start on http://localhost:5000


Terminal 2 (Frontend):

cd nse-scheduler-frontend
npm start
# The React app should open in your browser at http://localhost:3000


Tech Stack

Frontend: React.js, Tailwind CSS, React Router DOM

Backend: Node.js, Express.js, ts-node

AI Service: Python 3.12, FastAPI, Pydantic v2, sentence-transformers (all-MiniLM-L6-v2)

Database: MongoDB, Mongoose, MongoDB Atlas Vector Search

## Estimation Engine Documentation

| Document | Purpose |
|---|---|
| [docs/estimation-engine/user_manual.md](docs/estimation-engine/user_manual.md) | How to use the Duration and Manpower calculators, including AI efficiency inference |
| [docs/estimation-engine/test_plan.md](docs/estimation-engine/test_plan.md) | Test strategy, environment, and test cases for the estimation/prediction feature |
