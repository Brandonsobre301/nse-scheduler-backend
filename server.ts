/*This file starts the web server, connects to the database, and sets up routes for user actions.*/
import express, { Application } from 'express'; 
import cors from 'cors';
import dotenv from 'dotenv';
import './config/db';
import userRoutes  from './routes/userRoutes';
import projectRoutes from './routes/projectRoutes'; 

dotenv.config();

// Create the express app
const app: Application = express();
const port = process.env.PORT || 5000; // Use port 5000 to avoid conflict with React

// Middleware 
app.use(express.json());
app.use(
    cors({
    origin: 'http://localhost:3000', // Your React app's URL
    credentials: true
    })
);


// Mounting statements
// Tells Express application that any request with URL starts with /auth should be handled by the UserRouter
app.use('/auth', userRoutes);
app.use('/projects', projectRoutes);

//Start the server
app.listen(port, () => {
    console.log(`✅ Server is running on port ${port}`);
});
