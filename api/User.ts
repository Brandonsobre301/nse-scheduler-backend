/*This file handles user login by checking the email and password against the database and responds with success or error messages.*/
import express, { Request, Response } from 'express';
import bcrypt from 'bcrypt';
import jwt from 'jsonwebtoken';
import UserModel, { User } from '../models/User';
import ProjectModel from '../models/Project';

// Initialize router
const router = express.Router();

// Sign-up route
router.post('/signup', async (req: Request, res: Response) => {
    try {
        let { name, email, password, dateOfBirth } = req.body;
        
        // Trim all inputs
        name = (name || '').trim();
        email = (email || '').trim();
        password = (password || '').trim();
        dateOfBirth = (dateOfBirth || '').trim();

        // Check for empty values AFTER trimming
        if (!name) {
            return res.status(400).json({ status: 'error', message: 'Name is required' });
        }




        if (!email) {
            return res.status(400).json({ status: 'error', message: 'Email is required' });
        }
        if (!password) {
            return res.status(400).json({ status: 'error', message: 'Password is required' });
        }
        if (!dateOfBirth) {
            return res.status(400).json({ status: 'error', message: 'Date of birth is required' });
        }

        // Validate formats
        if (!/^[a-zA-Z ]+$/.test(name)) {
            return res.status(400).json({ status: 'error', message: 'Name can only contain letters and spaces' });
        }
        if (!/^[\w\-\.]+@([\w\-]+\.)+[\w\-]{2,4}$/.test(email)) {
            return res.status(400).json({ status: 'error', message: 'Invalid email format' });
        }
        if (!new Date(dateOfBirth).getTime()) {
            return res.status(400).json({ status: 'error', message: 'Invalid date of birth' });
        }
        if (password.length < 8) {
            return res.status(400).json({ status: 'error', message: 'Password must be at least 8 characters' });
        }

        // Check for existing user
        const existingUser = await UserModel.findOne({ email }).exec();
        if (existingUser) {
            return res.status(400).json({ status: 'error', message: 'Email already exists' });
        }

        // Create user
        const hashedPassword = await bcrypt.hash(password, 10);
        const newUser = new UserModel({ 
            name, 
            email, 
            password: hashedPassword, 
            dateOfBirth,
            role: 'viewer'
        });
        const savedUser = await newUser.save();

        // Generate token
        const token = jwt.sign(
            { 
                userId: savedUser.id,
                email: savedUser.email,
                name: savedUser.name,
                role: savedUser.role || 'viewer'
            }, 
            process.env.JWT_SECRET!, 
            { expiresIn: '7d' }
        );

        res.json({ 
            status: 'success', 
            message: 'User registered successfully',
            token,
            user: {
                id: savedUser.id,
                name: savedUser.name,
                email: savedUser.email,
                role: savedUser.role || 'viewer'
            }
        });
    } catch (err) {
        console.error(err);
        res.status(500).json({ status: 'error', message: 'Server error' });
    }
});

// Login route
router.post('/login', async (req: Request, res: Response) => {
    try {
        let { email, password } = req.body;
        
        // Trim inputs
        email = (email || '').trim();
        password = (password || '').trim();

        // Validate
        if (!email) {
            return res.status(400).json({ message: 'Email is required' });
        }
        if (!password) {
            return res.status(400).json({ message: 'Password is required' });
        }
        if (!/^[\w\-\.]+@([\w\-]+\.)+[\w\-]{2,4}$/.test(email)) {
            return res.status(400).json({ message: 'Invalid email format' });
        }

        // Find user
        const user = await UserModel.findOne({ email }).exec();
        if (!user) {
            return res.status(401).json({ message: 'Invalid credentials' });
        }

        // Check password
        const isMatch = await bcrypt.compare(password, user.password);
        if (!isMatch) {
            return res.status(401).json({ message: 'Invalid password' });
        }

        // Generate token with flat structure
        const token = jwt.sign(
            { 
                userId: user.id,
                email: user.email,
                name: user.name,
                role: user.role || 'viewer'
            }, 
            process.env.JWT_SECRET!, 
            { expiresIn: '7d' }
        );

        res.status(200).json({
            message: 'User signed in successfully',
            token,
            user: { 
                id: user.id, 
                name: user.name, 
                email: user.email,
                role: user.role || 'viewer'
            }
        });
    } catch (err) {
        console.error(err);
        res.status(500).json({ message: 'Server error' });
    }
});

// GET /auth/profile
router.get('/profile', async (req: Request, res: Response) => {
    try {
        const token = req.header('Authorization')?.replace('Bearer ', '');
        if (!token) return res.status(401).json({ message: 'No token, authorization denied' });

        const decoded = jwt.verify(token, process.env.JWT_SECRET!) as any;
        const user = await UserModel.findById(decoded.userId).select('-password').exec();
        if (!user) return res.status(404).json({ message: 'User not found' });

        res.json(user);
    } catch (err) {
        res.status(401).json({ message: 'Token is not valid' });
    }
});

// PUT /auth/profile
router.put('/profile', async (req: Request, res: Response) => {
    try {
        const token = req.header('Authorization')?.replace('Bearer ', '');
        if (!token) return res.status(401).json({ message: 'No token, authorization denied' });

        const decoded = jwt.verify(token, process.env.JWT_SECRET!) as any;
        const { name, dateOfBirth } = req.body;

        const updatedUser = await UserModel.findByIdAndUpdate(
            decoded.userId,
            { name, dateOfBirth },
            { new: true }
        ).select('-password').exec();

        res.json({ message: 'Profile updated successfully', user: updatedUser });
    } catch (err) {
        console.error(err);
        res.status(500).json({ message: 'Server error' });
    }
});

// PUT /auth/:id/scope
router.put('/:id/scope', async (req: Request, res: Response) => {
    try {
        const { scope } = req.body;
        const project = await ProjectModel.findByIdAndUpdate(
            req.params.id,
            { scope },
            { new: true }
        ).exec();
        res.json(project);
    } catch (err) {
        console.error(err);
        res.status(500).send('Server error');
    }
});

export default router;