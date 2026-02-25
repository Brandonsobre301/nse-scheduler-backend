NSE Resource Scheduler

A centralized operations dashboard and resource planning tool designed to bridge the gap between office scheduling and field execution.

Features

Authentication: Secure login and registration with Role-Based Access Control (RBAC).

Project Management: Full CRUD operations for active job sites.

Resource Calculators: Algorithms to calculate required manpower vs. project duration.

Live Operations Dashboard: Real-time matrix of active phases, manpower distribution, and site status (Green/Yellow/Red indicators).

Prerequisites

To run this application on your local machine, you will need:

Node.js (v16 or higher)

MongoDB (Running locally or a MongoDB Atlas URI)

Installation & Setup

1. Clone the Repository

git clone <your-github-repo-url>
cd <your-repo-name>


2. Environment Variables

You need to set up your local environment variables. Create a .env file in the root of your backend folder and add the following:

PORT=5000
MONGO_URI=your_mongodb_connection_string_here
JWT_SECRET=your_super_secret_jwt_key


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

Database: MongoDB, Mongoose
