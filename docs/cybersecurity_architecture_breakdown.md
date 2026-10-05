# Frontend vs. Backend Security Matrix for NSE Scheduler

In a distributed microservice architecture like the **NSE Scheduler** (React $\rightarrow$ Express $\rightarrow$ FastAPI $\rightarrow$ MongoDB Atlas), a core security rule applies: **never trust the client**.

Frontend checks exist purely for **User Experience (UX)**. Real security, data protection, and mathematical integrity must be strictly enforced on the **Backend (Express + FastAPI)**.

## 1. Quick Responsibility Matrix

| Security Concern | React Frontend (:3000) | Express Gateway (:5000) | FastAPI Engine (:8000) | 
 | ----- | ----- | ----- | ----- | 
| **Network Boundary** | Call *only* Express endpoints (`/api/v1/estimate`) | Proxy to internal Docker DNS (`ai-service:8000`) | Bind strictly to internal Docker network | 
| **Authentication & JWT** | Attach `Bearer <token>` to headers; clear on logout | Validate signature, expiration, and claims | Trust injected headers (`X-User-ID`, `X-User-Role`) | 
| **Authorization (BOLA / IDOR)** | Hide restricted UI buttons/links | Verify user has access to requested project `_id` | N/A (operates on pre-verified requests) | 
| **Input Validation & Types** | Form restrictions (min, max, disabled buttons) | Enforce payload size limits (e.g., max 100kb) | **Strict Pydantic v2 validation** (reject negative numbers/bad types) | 
| **NoSQL / Vector Injection** | N/A | Reject malformed JSON bodies | Build query objects with typed BSON dictionaries | 
| **Denial of Service / Wallet** | Disable submit buttons during inference | Rate-limit requests per IP/User | Truncate query strings before embedding | 
| **XSS & Output Sanitization** | Escape and safely render MongoDB text | Set secure HTTP headers (`Helmet`) | N/A | 
| **Error Handling & Disclosure** | Display clean, user-friendly error banners | Mask raw internal 500 errors | Return clean JSON responses; strip stack traces | 

## 2. Frontend (React @ `:3000`) Responsibilities

The browser environment is completely public and under client control. Anyone can open DevTools, modify JavaScript variables, or send requests through Postman. Therefore, frontend controls are strictly **defensive UX**:




## 3. Backend Layer 1: Express API Gateway (`:5000`)

The Express container is your **Perimeter Security Shield**. Its job is to authenticate, rate limit, and block hostile requests *before* they reach your Python AI container or MongoDB.

### What Goes in Express:

1. **Strict CORS Policy:**

   * Restrict Cross-Origin Resource Sharing exclusively to the frontend origin (e.g., `http://localhost:3000`).

2. **JWT Signature & Expiration Verification:**

   * Intercept every mutation or estimation route with `middleware/auth.ts`.

   * Verify the token's cryptographic signature, expiration timestamp, and issuer.

3. **Header Sanitization & Downstream Injection:**

   * Strip any client-supplied internal headers (e.g., remove any incoming `X-User-Role` from the client).

   * Once Express verifies the JWT, inject verified metadata into the proxy request headers downstream to Python (e.g., `X-User-ID: 65a...`, `X-User-Role: estimator`).

4. **Broken Object-Level Authorization (BOLA/IDOR Defense):**

   * When a user requests project details or updates an estimate via `_id`, query MongoDB or check claims to confirm that the user's company or team actually owns that record.

5. **Rate Limiting & Payload Limits:**

   * Apply `express-rate-limit` on `/api/v1/estimate` to prevent automated scripts from spamming the compute-intensive embedding engine.

   * Enforce payload limits (`express.json({ limit: '100kb' })`) to prevent memory exhaustion attacks.

6. **Network Boundary Enforcement:**

   * The proxy target must be hardcoded to `http://ai-service:8000` via the internal Docker bridge (`app-net`). Never allow the target URL to be manipulated via request headers (preventing Server-Side Request Forgery / SSRF).

## 4. Backend Layer 2: FastAPI Microservice (`:8000`)

The Python service is your **Core Reasoning & Calculation Engine**. It sits behind the Express firewall. Its job is input schema enforcement, deterministic mathematical safety, and safe communication with MongoDB Atlas.

### What Goes in FastAPI:

1. **Network Isolation (Zero Public Binding):**

   * In `docker-compose.yml`, use `expose: - "8000"`, NOT `ports: - "8000:8000"`. The FastAPI service should not be accessible from the host machine or public internet.

2. **Strict Type Safety & Schema Validation (Pydantic v2):**

   * Never process raw dictionaries.

   * Enforce schemas where $H > 0$, $MP > 0$, and $T > 0$ using Pydantic fields (`gt=0`).

   * Reject unexpected fields using `model_config = ConfigDict(extra='forbid')`.

3. **Deterministic Mathematical Guardrails:**

   * Intercept efficiency values before running formulas: clamp $E \le 1.0$ (or $E \le 2.0$ depending on operational policy) and check for division-by-zero scenarios.

4. **Denial-of-Compute Prevention (Embedding Truncation):**

   * In `embedder.py`, explicitly truncate raw query text (e.g., `query[:512]`) before invoking `all-MiniLM-L6-v2`. This prevents large payload attacks designed to spike CPU usage.

5. **NoSQL & Vector Search Pipeline Hardening:**

   * Never construct MongoDB queries or Atlas Vector Search aggregation pipelines using Python f-strings or string concatenation.

   * Pass variables through strongly typed BSON dictionary structures and cast numeric filters (such as square footage bounds) explicitly to `float`.

6. **Error Masking & Information Disclosure:**

   * Configure global FastAPI exception handlers so that internal database exceptions or PyTorch warnings log internally to Docker logs, but return only clean, generic error messages to Express (e.g., `{"error": "Estimation calculation failed", "warnings": [...]}`).

## 5. Summary: The Journey of a Secure Request

```
[User Form in React]
   │  • Validates inputs locally for responsive UI feedback
   │  • Attaches Bearer JWT
   ▼
[POST :5000/api/v1/estimate (Express Gateway)]
   │  • Validates CORS and checks rate limits
   │  • Cryptographically verifies JWT token & user permissions
   │  • Strips untrusted headers; sets X-User-ID
   │  • Proxies across internal Docker app-net
   ▼
[POST :8000/estimate (FastAPI Engine)]
   │  • Validates Pydantic schema (H > 0, MP > 0)
   │  • Truncates text to safe length (< 512 chars)
   │  • Runs local all-MiniLM-L6-v2 embedding
   ▼
[MongoDB Atlas Vector Search]
   │  • Runs deterministic cosine math & retrieves matches
   ▼
[FastAPI Engine Math Execution]
   │  • Applies clamp guardrails (E <= 1.0)
   │  • Runs Mode 1 or Mode 2 formulas
   │  • Returns clean JSON with outputs and warnings[]


```