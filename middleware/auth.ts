// middleware/auth.ts
import { Request, Response, NextFunction } from 'express';
import jwt, { Algorithm, JwtPayload } from 'jsonwebtoken';

export type UserRole = 'admin' | 'manager' | 'viewer';
const VALID_ROLES: ReadonlySet<string> = new Set(['admin', 'manager', 'viewer']);

// Pin the algorithm this app actually signs with (api/User.ts uses the
// jsonwebtoken default, HS256). Without an explicit allowlist, jwt.verify()
// accepts whatever `alg` the token header claims — the classic "algorithm
// confusion" bypass for HS256 secrets.
const ALLOWED_ALGORITHMS: Algorithm[] = ['HS256'];

export interface AuthRequest extends Request {
    userId?: string;
    user?: { id: string; role: UserRole };
}

interface VerifiedTokenPayload extends JwtPayload {
    userId: string;
    email?: string;
    role?: string;
}

// A validly-signed token can still carry a missing/malformed payload —
// never trust decoded fields without this check.
function hasRequiredClaims(payload: string | JwtPayload): payload is VerifiedTokenPayload {
    return (
        typeof payload === 'object' &&
        payload !== null &&
        typeof (payload as VerifiedTokenPayload).userId === 'string' &&
        (payload as VerifiedTokenPayload).userId.length > 0
    );
}

export default function auth(req: AuthRequest, res: Response, next: NextFunction) {
    const authHeader = req.header('Authorization');

    // Require the literal "Bearer <token>" scheme — reject bare/other-scheme tokens.
    if (!authHeader?.startsWith('Bearer ')) {
        return res.status(401).json({ message: 'No token, authorization denied' });
    }
    const token = authHeader.slice('Bearer '.length).trim();
    if (!token) {
        return res.status(401).json({ message: 'No token, authorization denied' });
    }

    try {
        const decoded = jwt.verify(token, process.env.JWT_SECRET!, {
            algorithms: ALLOWED_ALGORITHMS, // reject alg-confusion / "none" tokens
            clockTolerance: 5,              // small skew allowance, not an expiry bypass
            maxAge: '7d',                    // defense-in-depth on top of the token's own `exp`
        });

        if (!hasRequiredClaims(decoded)) {
            return res.status(401).json({ message: 'Token is not valid' });
        }

        // Never trust an arbitrary role string from the payload — fall back to
        // the least-privileged role if it isn't one we recognize.
        const role: UserRole = VALID_ROLES.has(decoded.role ?? '')
            ? (decoded.role as UserRole)
            : 'viewer';

        req.userId = decoded.userId;
        req.user = { id: decoded.userId, role };
        next();
    } catch (err) {
        // No logging of token contents/claims — auth failures are routine
        // traffic, and token fragments must never land in shared logs.
        res.status(401).json({ message: 'Token is not valid' });
    }
}