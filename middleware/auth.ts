import { Request, Response, NextFunction } from 'express';  
import jwt from 'jsonwebtoken';

export interface AuthRequest extends Request {
    user?: {id : string };  
}

export default function auth(req: AuthRequest, res: Response, next: NextFunction) {
    const token = req.header('Authorization')?.replace('Bearer', '');
    if(!token) return res.status(401).json({message: 'No Token, authorization denied'});    

    try{
        const decoded = jwt.verify(token, process.env.JWT_SECRET || '') as any; 
        req.user = decoded.user;
        next();
    } catch(err){
        res.status(401).json({message: 'Token is not valid'});
    }
}