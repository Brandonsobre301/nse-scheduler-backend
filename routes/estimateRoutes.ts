/**
 * estimateRoutes.ts — Authenticated proxy from Node.js backend to the
 * FastAPI estimation microservice.
 *
 * Traffic flow:
 *   Client → Nginx → Node.js (JWT verified here) → ai-service:8000 (internal)
 *
 * The FastAPI service has no auth of its own — it is unreachable outside
 * the Docker app-net bridge network. Authentication is enforced here.
 */

import { Router, Request, Response } from 'express';
import auth from '../middleware/auth';

const router = Router();

const AI_SERVICE_URL =
    process.env.AI_SERVICE_URL || 'http://ai-service:8000';

/**
 * POST /api/v1/estimate
 *
 * Proxies the estimation request to the FastAPI service and returns
 * its response verbatim. The JWT must be valid to reach this route.
 *
 * Request body: EstimationRequest (see ai-service/models/estimation.py)
 * Response:     EstimationResponse or ErrorDetail (400/422/500)
 */
router.post('/estimate', auth, async (req: Request, res: Response) => {
    const target = `${AI_SERVICE_URL}/api/v1/estimate`;

    let aiResponse: globalThis.Response;

    try {
        aiResponse = await fetch(target, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
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
    const data = await aiResponse.json();
    res.status(aiResponse.status).json(data);
});

export default router;
