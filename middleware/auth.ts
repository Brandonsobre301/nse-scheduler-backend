// middleware/auth.ts
import { Request, Response, NextFunction } from 'express';  
import jwt from 'jsonwebtoken';

export interface AuthRequest extends Request {
    userId?: string;
    user?: { id: string; role?: 'admin' | 'manager' | 'viewer' };  
}

export default function auth(req: AuthRequest, res: Response, next: NextFunction) {
    console.log('\n🔍 Auth middleware called for:', req.method, req.path);
    
    const authHeader = req.header('Authorization');
    console.log('  - Auth header received:', authHeader ? authHeader.substring(0, 30) + '...' : 'NONE');
    
    const token = authHeader?.replace('Bearer ', '').trim();
    
    if (!token) {
        console.error('  ❌ No token found in request');
        return res.status(401).json({ message: 'No token, authorization denied' });
    }

    console.log('  - Token extracted (first 30 chars):', token.substring(0, 30) + '...');

    try {
        const decoded = jwt.verify(token, process.env.JWT_SECRET!) as any;
        
        console.log('  ✅ Token decoded successfully:');
        console.log('    - userId:', decoded.userId);
        console.log('    - email:', decoded.email);
        console.log('    - role:', decoded.role);
        
        req.userId = decoded.userId;
        req.user = {
            id: decoded.userId,
            role: decoded.role || 'viewer'
        };
        
        console.log('  ✅ Auth successful, calling next()');
        next();
    } catch (err: any) {
        console.error('  ❌ Token verification failed:', err.message);
        res.status(401).json({ message: 'Token is not valid' });
    }
}