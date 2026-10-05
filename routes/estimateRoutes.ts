/**
 * estimateRoutes.ts — Authenticated proxy from Node.js backend to the
 * FastAPI estimation microservice.
 *
 * Traffic flow:
 *   Client → Nginx → Node.js (JWT verified here) → ai-service:8000 (internal)
 *
 * Security invariants enforced in this file:
 *   1. `auth` must pass before the handler runs at all.
 *   2. Outbound headers are an explicit allowlist — no client header is forwarded as-is.
 *   3. The proxy target is a boot-time-validated constant — never derived from request data.
 *   4. Body size is capped upstream (see server.ts) before this handler ever runs.
 */

import { Router, Response } from 'express';
import rateLimit from 'express-rate-limit';
import auth, { AuthRequest } from '../middleware/auth';

const router = Router();

// Network boundary — resolved and validated ONCE at module load, never per-request.
// This is what stops SSRF via host-header tampering or a spoofed target: the
// destination is a fixed constant, not derived from `req` in any way.
const DEFAULT_AI_SERVICE_URL = 'http://ai-service:8000';
const ALLOWED_AI_SERVICE_HOSTS = new Set(['ai-service', 'localhost', '127.0.0.1']);

function assertTrustedAiServiceOrigin(rawUrl: string): string {
    let parsed: URL;
    try {
        parsed = new URL(rawUrl);
    } catch {
        throw new Error(`AI_SERVICE_URL "${rawUrl}" is not a valid URL. Refusing to start.`);
    }
    // Only plain HTTP to a known internal Docker DNS name/loopback is allowed.
    if (parsed.protocol !== 'http:' || !ALLOWED_AI_SERVICE_HOSTS.has(parsed.hostname)) {
        throw new Error(
            `AI_SERVICE_URL "${rawUrl}" is not an allowed internal target. Refusing to start.`
        );
    }
    return parsed.origin;
}

const AI_SERVICE_ORIGIN = assertTrustedAiServiceOrigin(
    process.env.AI_SERVICE_URL || DEFAULT_AI_SERVICE_URL
);
const AI_SERVICE_API_KEY = process.env.AI_SERVICE_API_KEY || '';

// The embedding calculation (all-MiniLM-L6-v2) is CPU-expensive — cap how
// often any single client can trigger it, independent of JWT validity.
const estimateLimiter = rateLimit({
    windowMs: 60 * 1000,
    limit: 20,
    standardHeaders: true,
    legacyHeaders: false,
    message: { status: 'error', message: 'Too many estimate requests. Please slow down and try again.' },
});

/**
 * POST /api/v1/estimate
 *
 * Proxies the estimation request to the FastAPI service and returns
 * its response verbatim. The JWT must be valid to reach this route.
 *
 * Request body: EstimationRequest (see ai-service/models/estimation.py)
 * Response:     EstimationResponse or ErrorDetail (400/422/500)
 */
router.post('/estimate', auth, estimateLimiter, async (req: AuthRequest, res: Response) => {
    const target = `${AI_SERVICE_ORIGIN}/api/v1/estimate`;

    // Explicit outbound header allowlist. Any client-supplied X-User-*/
    // X-Internal-* headers are dropped here by construction — identity is
    // re-derived only from the verified JWT (`req.user`), never from raw headers.
    const outboundHeaders: Record<string, string> = {
        'Content-Type': 'application/json',
        'X-Internal-Api-Key': AI_SERVICE_API_KEY,
        'X-User-Id': req.user?.id ?? '',
        'X-User-Role': req.user?.role ?? 'viewer',
    };

    let aiResponse: globalThis.Response;

    try {
        aiResponse = await fetch(target, {
            method: 'POST',
            headers: outboundHeaders,
            body: JSON.stringify(req.body),
        });
    } catch (err) {
        // Network-level failure (ai-service down, DNS resolution failure, etc.)
        console.error('[estimateRoutes] Failed to reach ai-service:', err);
        res.status(503).json({
            status: 'error',
            message: 'Estimation service is unavailable. Please try again later.',
        });
        return;
    }

    // Surface the FastAPI response status and body directly to the client.
    // This preserves 400 (semantic errors), 422 (schema validation), and 200.
    let data: unknown;
    try {
        data = await aiResponse.json();
    } catch (err) {
        // ai-service returned a non-JSON body (e.g. an upstream error page) —
        // don't let the raw body/parse error leak back to the client.
        console.error('[estimateRoutes] Failed to parse ai-service response:', err);
        res.status(502).json({
            status: 'error',
            message: 'Received an invalid response from the estimation service.',
        });
        return;
    }
    res.status(aiResponse.status).json(data);
});

export default router;
