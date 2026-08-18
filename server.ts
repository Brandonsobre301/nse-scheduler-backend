/*This file starts the web server, connects to the database, and sets up routes for user actions.*/
import express, { Application } from 'express'; 
import cors from 'cors';
import dotenv from 'dotenv';
import './config/db';
import userRoutes from './api/User';  //  CHANGED: Use api/User.ts (has validation)
import projectRoutes from './routes/projectRoutes';
import estimateRoutes from './routes/estimateRoutes';

dotenv.config();

// Create the express app
const app: Application = express();
const port = process.env.PORT || 5000;

// Validate required env vars
if (!process.env.JWT_SECRET) {
    console.error('❌ FATAL: JWT_SECRET environment variable is not set');
    process.exit(1);
}

// Middleware 
app.use(express.json());
const allowedOrigins = (process.env.CORS_ORIGIN || 'http://localhost:3000')
    .split(',')
    .map(o => o.trim());
app.use(
    cors({
    origin: (origin, callback) => {
        // Allow requests with no origin (e.g. curl, Postman, server-to-server)
        if (!origin || allowedOrigins.includes(origin)) return callback(null, true);
        callback(new Error(`CORS: origin ${origin} not allowed`));
    },
    credentials: true
    })
);

// Mounting statements
app.use('/auth', userRoutes);  // Now uses api/User.ts with validation
app.use('/projects', projectRoutes);
app.use('/api/v1', estimateRoutes);

// Start the server
app.listen(port, () => {
    console.log(`✅ Server is running on port ${port}`);
});
