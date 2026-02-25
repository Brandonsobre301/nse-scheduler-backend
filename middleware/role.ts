import { Response, NextFunction } from 'express';
import { AuthRequest } from './auth';


export type UserRole = 'admin' | 'manager' | 'viewer';

export function requireRole(...allowedRoles: UserRole[]) {
  return (req: AuthRequest, res: Response, next: NextFunction) => {
    const userRole = req.user?.role as UserRole;

    if (!userRole) {
      return res.status(401).json({ message: 'Authentication required' });
    }

    if (!allowedRoles.includes(userRole)) {
      return res.status(403).json({ 
        message: `Access denied. Required role: ${allowedRoles.join(' or ')}`,
        yourRole: userRole 
      });
    }

    next();
  };
}