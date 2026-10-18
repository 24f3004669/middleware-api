import math
import time
import uuid
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

EMAIL = "24f3004669@ds.study.iitm.ac.in"
ASSIGNED_ORIGIN = "https://app-3lqsfk.example.com"
EXAM_ORIGIN = "PASTE_EXAM_PAGE_ORIGIN_HERE"   # <-- replace with the value from Step 1

RATE_LIMIT = 12       # B requests
WINDOW = 10.0         # per 10 seconds

ALLOWED_ORIGINS = [ASSIGNED_ORIGIN]
if EXAM_ORIGIN.startswith("http"):
    ALLOWED_ORIGINS.append(EXAM_ORIGIN.rstrip("/"))

app = FastAPI()

request_times = defaultdict(deque)   # client id -> timestamps of recent requests


# ---------- Middleware 3: per-client rate limit (innermost) ----------
@app.middleware("http")
async def rate_limiter(request: Request, call_next):
    client_id = request.headers.get("x-client-id")
    if client_id and request.method != "OPTIONS":
        now = time.monotonic()
        q = request_times[client_id]
        while q and now - q[0] >= WINDOW:          # forget requests older than 10s
            q.popleft()
        if len(q) >= RATE_LIMIT:
            retry_after = max(1, math.ceil(WINDOW - (now - q[0])))
            return JSONResponse(
                status_code=429,
                content={"detail": "Too Many Requests"},
                headers={"Retry-After": str(retry_after)},
            )
        q.append(now)
    return await call_next(request)


# ---------- Middleware 1: request context (wraps the rate limiter) ----------
@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ---------- Middleware 2: CORS (outermost, so every reply gets CORS headers) ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,               # exact list, no "*"
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Retry-After"],   # lets the browser READ these headers
)


@app.get("/ping")
async def ping(request: Request):
    return {"email": EMAIL, "request_id": request.state.request_id}


@app.get("/")
async def home():
    return {"status": "ok", "use": "GET /ping"}