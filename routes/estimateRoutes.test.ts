/**
 * estimateRoutes.test.ts — proxy/auth boundary tests for the Express layer.
 *
 * Uses Node's built-in test runner — no new npm dependency. Compiled by the
 * existing `tsc` build (routes/**\/*.ts is already in tsconfig.json's include
 * list) and run via `npm test` (see package.json).
 *
 * Traceability: docs/estimation-engine/test_plan.md §6.6 (TC-P01, TC-P03, TC-P04).
 * The router's outbound `fetch` to ai-service is mocked per-test; the test's
 * own calls to the local in-process Express server use `node:http` directly
 * so the two never collide on the same global.fetch mock.
 */

import assert from 'node:assert/strict';
import test from 'node:test';
import http, { Server } from 'node:http';
import jwt from 'jsonwebtoken';
import express from 'express';

process.env.JWT_SECRET ??= 'test-jwt-secret-for-estimateRoutes-tests';
process.env.AI_SERVICE_API_KEY = 'test-internal-key';
process.env.AI_SERVICE_URL = 'http://ai-service:8000'; // must pass the hostname allowlist

// Required (not `import`ed) so it reads the env vars above at module-load
// time, matching estimateRoutes.ts's real startup behavior (it resolves
// AI_SERVICE_ORIGIN/AI_SERVICE_API_KEY once at module scope).
// eslint-disable-next-line @typescript-eslint/no-var-requires
const estimateRoutes = require('./estimateRoutes').default;

function buildTestApp() {
    const app = express();
    app.use(express.json());
    app.use('/api/v1', estimateRoutes);
    return app;
}

function validToken(): string {
    return jwt.sign({ userId: 'u1', role: 'manager' }, process.env.JWT_SECRET!, {
        algorithm: 'HS256',
        expiresIn: '1h',
    });
}

function listen(app: express.Express): Promise<{ server: Server; port: number }> {
    return new Promise((resolve) => {
        const server = app.listen(0, () => {
            const address = server.address();
            const port = typeof address === 'object' && address ? address.port : 0;
            resolve({ server, port });
        });
    });
}

function postJson(
    port: number,
    headers: Record<string, string>,
    body: unknown
): Promise<{ status: number; body: any }> {
    return new Promise((resolve, reject) => {
        const payload = JSON.stringify(body);
        const req = http.request(
            {
                hostname: '127.0.0.1',
                port,
                path: '/api/v1/estimate',
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Content-Length': Buffer.byteLength(payload),
                    ...headers,
                },
            },
            (res) => {
                let raw = '';
                res.on('data', (chunk) => (raw += chunk));
                res.on('end', () => {
                    try {
                        resolve({ status: res.statusCode ?? 0, body: raw ? JSON.parse(raw) : null });
                    } catch (err) {
                        reject(err);
                    }
                });
            }
        );
        req.on('error', reject);
        req.write(payload);
        req.end();
    });
}

const SAMPLE_BODY = {
    projectId: 'PROJ-1',
    calculationMode: 'duration',
    inputs: { totalManHours: 4800, desiredManpower: 6, assumedEfficiency: 0.85 },
};

test('TC-P01 — missing Authorization header is rejected before ai-service is ever called', async () => {
    const originalFetch = global.fetch;
    let fetchCalled = false;
    global.fetch = (async () => {
        fetchCalled = true;
        throw new Error('fetch should not be called');
    }) as typeof fetch;

    const app = buildTestApp();
    const { server, port } = await listen(app);
    try {
        const { status } = await postJson(port, {}, SAMPLE_BODY);
        assert.equal(status, 401);
        assert.equal(fetchCalled, false);
    } finally {
        server.close();
        global.fetch = originalFetch;
    }
});

test('invalid JWT is rejected with 401', async () => {
    const app = buildTestApp();
    const { server, port } = await listen(app);
    try {
        const { status } = await postJson(port, { Authorization: 'Bearer not-a-real-token' }, SAMPLE_BODY);
        assert.equal(status, 401);
    } finally {
        server.close();
    }
});

test("TC-P04 — valid JWT + healthy ai-service: Express returns FastAPI's body/status verbatim", async () => {
    const originalFetch = global.fetch;
    const fakeAiResponse = {
        status: 'success',
        projectId: 'PROJ-1',
        calculationMode: 'duration',
        outputs: {
            realisticDurationWeeks: 20,
            totalExpendedHours: 4800,
            recommendedManpower: null,
            calculatedEfficiency: 0.85,
            efficiencySource: 'provided',
            warnings: [],
        },
    };
    global.fetch = (async () =>
        new Response(JSON.stringify(fakeAiResponse), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
        })) as unknown as typeof fetch;

    const app = buildTestApp();
    const { server, port } = await listen(app);
    try {
        const { status, body } = await postJson(port, { Authorization: `Bearer ${validToken()}` }, SAMPLE_BODY);
        assert.equal(status, 200);
        assert.deepEqual(body, fakeAiResponse);
    } finally {
        server.close();
        global.fetch = originalFetch;
    }
});

test('TC-P03 — ai-service unreachable returns 503, not a raw network error', async () => {
    const originalFetch = global.fetch;
    global.fetch = (async () => {
        throw new Error('ECONNREFUSED (simulated)');
    }) as unknown as typeof fetch;

    const app = buildTestApp();
    const { server, port } = await listen(app);
    try {
        const { status, body } = await postJson(port, { Authorization: `Bearer ${validToken()}` }, SAMPLE_BODY);
        assert.equal(status, 503);
        assert.equal(body.status, 'error');
    } finally {
        server.close();
        global.fetch = originalFetch;
    }
});

test('ai-service returns a non-JSON body -> Express returns 502, not a raw parse error', async () => {
    const originalFetch = global.fetch;
    global.fetch = (async () =>
        new Response('<html>Bad Gateway</html>', {
            status: 200,
            headers: { 'Content-Type': 'text/html' },
        })) as unknown as typeof fetch;

    const app = buildTestApp();
    const { server, port } = await listen(app);
    try {
        const { status, body } = await postJson(port, { Authorization: `Bearer ${validToken()}` }, SAMPLE_BODY);
        assert.equal(status, 502);
        assert.equal(body.status, 'error');
    } finally {
        server.close();
        global.fetch = originalFetch;
    }
});
