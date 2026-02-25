/*This file starts the web server, connects to the database, and sets up routes for user actions.*/
import express, { Application } from 'express'; 
import cors from 'cors';
import dotenv from 'dotenv';
import './config/db';
import userRoutes from './api/User';  // ✅ CHANGED: Use api/User.ts (has validation)
import projectRoutes from './routes/projectRoutes'; 

dotenv.config();

// Create the express app
const app: Application = express();
const port = process.env.PORT || 5000;

// Middleware 
app.use(express.json());
app.use(
    cors({
    origin: 'http://localhost:3000',
    credentials: true
    })
);

// Mounting statements
app.use('/auth', userRoutes);  // Now uses api/User.ts with validation
app.use('/projects', projectRoutes);

// Start the server
app.listen(port, () => {
    console.log(`✅ Server is running on port ${port}`);
});
