# ai_search_api.py
import os
import io
import re
import json
import time
import base64
import datetime
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from fastapi import FastAPI, Cookie, Request, Response, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

from pdf_renderer import render_pdf

# Import Supabase authentication
from supabase_auth import (
    sign_in, sign_out, sign_up, get_user_from_token, refresh_session,
    request_password_reset, update_password, update_user_profile, resend_verification,
    admin_create_user, admin_invite_user, admin_set_user_status,
    admin_list_users, is_configured as supabase_configured, supabase_admin
)

# Import usage tracking (still using PostgreSQL)
from auth_models import log_usage, get_user_stats, get_all_users_stats, set_user_status

# =========================
# Boot + OpenAI client
# =========================
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# Default to a widely available model. Override via .env OPENAI_MODEL=...
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI(title="Legal-Tech Filter API", version="0.2.0", docs_url=None, redoc_url=None, openapi_url=None)

# Jinja2 templates for report generation
templates = Jinja2Templates(directory="templates")

# CORS — restrict to known origins only
ALLOWED_ORIGINS = [
    "https://legaltech-explorer.onrender.com",
    "http://127.0.0.1:5500",   # local dev (VS Code Live Server)
    "http://localhost:5500",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Security headers middleware
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        # Clickjacking protection (also covered by CSP frame-ancestors below)
        response.headers["X-Frame-Options"] = "DENY"
        # Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Limit referrer info sent to third parties
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Enforce HTTPS for 1 year (only meaningful in production)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # Content Security Policy:
        # - script-src: self + jsdelivr CDN (PapaParse + DOMPurify); unsafe-inline required for
        #   existing inline <script> blocks — blocks unknown remote script sources
        # - connect-src self: even if XSS fires, it cannot exfiltrate data to external servers
        # - frame-ancestors none: secondary clickjacking protection
        # Logos are static assets — cache aggressively in browser
        if request.url.path.startswith("/logos/"):
            response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=604800"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net us.i.posthog.com; "
            "style-src 'self' 'unsafe-inline' fonts.googleapis.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self' us.i.posthog.com; "
            "font-src 'self' fonts.gstatic.com; "
            "frame-ancestors 'none'; "
            "object-src 'none'; "
            "base-uri 'self';"
        )
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Mount static files for logos
app.mount("/logos", StaticFiles(directory="logos"), name="logos")
app.mount("/static", StaticFiles(directory="static"), name="static")

# =========================
# In-Memory Cache
# =========================
# Structure: { cache_key: {"data": ..., "expires": timestamp} }
_cache: Dict[str, dict] = {}
CACHE_TTL_SEARCH  = 60 * 5        # 5 minutes — search/query results (short: changes as we tune)
CACHE_TTL_REPORT  = 60 * 60 * 24  # 24 hours  — PDF reports (expensive to regenerate)
CACHE_TTL = CACHE_TTL_SEARCH       # default

def cache_get(key: str):
    entry = _cache.get(key)
    if entry and time.time() < entry["expires"]:
        return entry["data"]
    if entry:
        del _cache[key]
    return None

def cache_set(key: str, data, ttl: int = CACHE_TTL_SEARCH):
    _cache[key] = {"data": data, "expires": time.time() + ttl}

# =========================
# Rate Limiting
# =========================
# Store request timestamps per user: {user_email: [timestamp1, timestamp2, ...]}
rate_limit_store: Dict[str, List[float]] = defaultdict(list)

# Rate limit configuration
RATE_LIMIT_REQUESTS = 20  # Number of requests allowed
RATE_LIMIT_WINDOW = 60    # Time window in seconds (1 minute)

def check_rate_limit(user_email: str) -> bool:
    """
    Check if user has exceeded rate limit.
    Returns True if within limit, False if exceeded.
    """
    now = time.time()

    # Clean up old timestamps outside the window
    rate_limit_store[user_email] = [
        ts for ts in rate_limit_store[user_email]
        if now - ts < RATE_LIMIT_WINDOW
    ]

    # Check if user has exceeded the limit
    if len(rate_limit_store[user_email]) >= RATE_LIMIT_REQUESTS:
        return False

    # Add current timestamp
    rate_limit_store[user_email].append(now)
    return True

# =========================
# Auth Rate Limiting
# =========================
# Store: {(ip, endpoint): [timestamp, ...]}
auth_rate_limit_store: Dict[str, List[float]] = defaultdict(list)
# Store: {(ip, email): [failure_timestamp, ...]}
login_failure_store: Dict[str, List[float]] = defaultdict(list)

# Per-endpoint limits: (max_requests, window_seconds)
AUTH_RATE_LIMITS = {
    "login":               (5,  60),   # 5 attempts / minute
    "signup":              (3,  600),  # 3 attempts / 10 minutes
    "forgot-password":     (3,  3600), # 3 emails / hour
    "resend-verification": (3,  3600), # 3 emails / hour
    "refresh":             (10, 60),   # 10 refreshes / minute
    "exchange-token":      (5,  60),   # 5 exchanges / minute
    "update-password":     (5,  60),   # 5 attempts / minute
}

# Login lockout: block IP+email after this many failures within the window
LOGIN_LOCKOUT_MAX    = 10
LOGIN_LOCKOUT_WINDOW = 900  # 15 minutes


def get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For from reverse proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_auth_rate_limit(ip: str, endpoint: str) -> bool:
    """
    Sliding-window rate check for auth endpoints keyed by IP + endpoint name.
    Returns True if within limit, False if exceeded.
    """
    limit, window = AUTH_RATE_LIMITS.get(endpoint, (5, 60))
    key = f"{ip}:{endpoint}"
    now = time.time()

    auth_rate_limit_store[key] = [
        ts for ts in auth_rate_limit_store[key] if now - ts < window
    ]

    if len(auth_rate_limit_store[key]) >= limit:
        return False

    auth_rate_limit_store[key].append(now)
    return True


def check_login_lockout(ip: str, email: str) -> bool:
    """
    Returns True (allow) if the IP+email combination has not exceeded the
    failure threshold within LOGIN_LOCKOUT_WINDOW seconds.
    """
    key = f"{ip}:{email}"
    now = time.time()
    login_failure_store[key] = [
        ts for ts in login_failure_store[key] if now - ts < LOGIN_LOCKOUT_WINDOW
    ]
    return len(login_failure_store[key]) < LOGIN_LOCKOUT_MAX


def record_login_failure(ip: str, email: str) -> None:
    key = f"{ip}:{email}"
    login_failure_store[key].append(time.time())


def clear_login_failures(ip: str, email: str) -> None:
    key = f"{ip}:{email}"
    login_failure_store.pop(key, None)


# =========================
# Schema your UI understands
# =========================
SCHEMA_FIELDS: List[str] = [
    "Vendor Name", "Vendor Overview", "HQ", "Office Locations", "Regions Served",
    "Year Founded", "Product Name", "Product Description", "Languages Supported",
    "Legal Functionality", "Functionality Sub-Category",
    "Main problem solved", "Primary User Segment", "Maturity Entry Level",
    "Industry Focus", "AI Powered", "AI Platform Type", "Deployment Model",
    "Hosting Location", "Hosting Provider", "ISO Certifications",
    "Security & Compliance Certifications", "Pricing Model",
    "Approx. Price Range (AUD)", "Demo / Proof of Concept Available",
    "Adoption Level", "Ease of Purchase", "Customer Reviews",
    "Customer Feedback Rating", "Vendor Contact Details", "Vendor Website"
]

MULTI_FIELDS = {
    # Note: These are stored as multi-value in CSV but rendered as single dropdowns in UI
    "Regions Served", "Primary User Segment", "AI Platform Type",
    "ISO Certifications", "Security & Compliance Certifications"
}

# =========================
# Canonicalisation maps
# =========================
MAIN_CATEGORY_CANON = {
    "contract automation": "Contracting & Document Automation",
    "contract review": "Contracting & Document Automation",
    "contract": "Contracting & Document Automation",
    "document automation": "Contracting & Document Automation",
    "document": "Contracting & Document Automation",
    "esignature": "Contracting & Document Automation",
    "e-signature": "Contracting & Document Automation",
    "matter management": "Matter, Workflow & Intake Management",
    "matter": "Matter, Workflow & Intake Management",
    "workflow": "Matter, Workflow & Intake Management",
    "intake": "Matter, Workflow & Intake Management",
    "operations": "Legal Operations & Analytics",
    "analytics": "Legal Operations & Analytics",
    "ops": "Legal Operations & Analytics",
    "spend management": "Legal Operations & Analytics",
    "vendor management": "Legal Operations & Analytics",
    "ebilling": "Legal Operations & Analytics",
    "e-billing": "Legal Operations & Analytics",
    "outside counsel": "Outside Counsel & Spend Management",
    "compliance": "Compliance, Risk & Governance",
    "risk": "Compliance, Risk & Governance",
    "governance": "Corporate Governance & Entity Management",
    "entity management": "Corporate Governance & Entity Management",
    "litigation": "Litigation, Disputes & Investigations",
    "ediscovery": "Litigation, Disputes & Investigations",
    "e-discovery": "Litigation, Disputes & Investigations",
    "dispute": "Litigation, Disputes & Investigations",
    "ip": "Intellectual Property, Technology & Data",
    "intellectual property": "Intellectual Property, Technology & Data",
    "patent": "Intellectual Property, Technology & Data",
    "patents": "Intellectual Property, Technology & Data",
    "ip portfolio": "Intellectual Property, Technology & Data",
    "trademark": "Intellectual Property, Technology & Data",
    "copyright": "Intellectual Property, Technology & Data",
    "technology": "Intellectual Property, Technology & Data",
    "employment": "Employment & HR Legal Support",
    "hr": "Employment & HR Legal Support",
    "cross-border": "Cross-Border, Transactions & Deal Management",
    "transactions": "Cross-Border, Transactions & Deal Management",
    "deal management": "Cross-Border, Transactions & Deal Management",
    "m&a": "Cross-Border, Transactions & Deal Management",
    "mergers and acquisitions": "Cross-Border, Transactions & Deal Management",
    "deal": "Cross-Border, Transactions & Deal Management",
    "knowledge management": "Knowledge, Search & Precedent Management",
    "knowledge": "Knowledge, Search & Precedent Management",
    "search": "Knowledge, Search & Precedent Management",
    "precedent": "Knowledge, Search & Precedent Management",
    "document management": "Knowledge, Search & Precedent Management",
    "ai assistant": "AI Legal Assistants & Productivity Tools",
    "assistant": "AI Legal Assistants & Productivity Tools",
    "productivity": "AI Legal Assistants & Productivity Tools",
    "integration": "Integration & Platform Infrastructure",
    "legal research": "Legal Research & Knowledge",
    "research": "Legal Research & Knowledge",
}

USER_SEGMENT_CANON = {
    "in-house": "Corporate legal",
    "inhouse": "Corporate legal",
    "corporate": "Corporate legal",
    "private practice": "Private practice",
    "law firm": "Private practice",
    "alsp": "Alternative Legal Service Providers (ALSPs)",
    "legal ops": "Legal Operations Professionals",
    "ops": "Legal Operations Professionals",
    "procurement": "Contract Management Teams / Procurement",
    "compliance": "Compliance & Risk Teams",
    "risk": "Compliance & Risk Teams",
    "litigation": "Litigation / Disputes Teams",
    "dispute": "Litigation / Disputes Teams",
    "ip": "Intellectual Property Teams.",
}

class Query(BaseModel):
    query: str

class ComparisonRequest(BaseModel):
    tools: List[Dict[str, Any]]

# =========================
# Authentication Models
# =========================
class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    token: str
    password: str

class SignUpRequest(BaseModel):
    email: str
    password: str
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    company: Optional[str] = ""

class InviteRequest(BaseModel):
    email: str
    role: str = "user"
    client_id: Optional[str] = None

# =========================
# Authentication Dependency (Supabase)
# =========================
async def get_current_user(
    access_token: Optional[str] = Cookie(None, alias="sb_access_token"),
    authorization: Optional[str] = Header(None)
):
    """Dependency to get current authenticated user from Supabase JWT"""
    # Try to get token from Authorization header first, then cookie
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    elif access_token:
        token = access_token

    if not token:
        return None

    user = get_user_from_token(token)
    return user

async def require_auth(user: Optional[dict] = Depends(get_current_user)):
    """Dependency that requires authentication"""
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

async def require_admin(user: dict = Depends(require_auth)):
    """Dependency that requires admin role"""
    if user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

async def rate_limit_dependency(user: dict = Depends(require_auth)):
    """Dependency to enforce rate limiting on authenticated endpoints"""
    if not check_rate_limit(user['email']):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Maximum {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds."
        )
    return user

# =========================
# Helpers
# =========================
def coerce_value(key: str, val: Any):
    if key in MULTI_FIELDS:
        if val is None or val == "":
            return []
        if isinstance(val, list):
            return [str(x).strip() for x in val if str(x).strip()]
        return [x.strip() for x in str(val).split(",") if x.strip()]
    else:
        if val is None:
            return ""
        if isinstance(val, (list, dict)):
            if isinstance(val, list):
                return ", ".join(str(x) for x in val)
            return json.dumps(val)
        return str(val)

def canonicalize_main_category(val: str) -> str:
    s = (val or "").lower().strip()

    # If already a valid category, return as-is
    if val in MAIN_CATEGORY_CANON.values():
        return val

    # Try exact matches first (more specific)
    for k, target in MAIN_CATEGORY_CANON.items():
        if s == k:
            return target

    # Then try substring matches (less specific, might catch more)
    # Prioritize longer matches to avoid false positives
    matches = []
    for k, target in MAIN_CATEGORY_CANON.items():
        if k in s:
            matches.append((len(k), target))

    if matches:
        # Return the longest matching key's target
        matches.sort(reverse=True)
        return matches[0][1]

    return val

def canonicalize_user_segments(vals):
    if isinstance(vals, str):
        vals = [vals]
    out = []
    for v in (vals or []):
        if v in USER_SEGMENT_CANON.values():
            out.append(v); continue
        s = (v or "").lower()
        mapped = None
        for k, target in USER_SEGMENT_CANON.items():
            if k in s:
                mapped = target
                break
        out.append(mapped or v)
    seen, clean = set(), []
    for v in out:
        if v not in seen:
            seen.add(v); clean.append(v)
    return clean

def normalize_to_schema(model_obj: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    synonyms = {
        "location": "Regions Served",
        "locations": "Regions Served",
        "region": "Regions Served",
        "regions": "Regions Served",
        "target_audience": "Primary User Segment",
        "audience": "Primary User Segment",
        "users": "Primary User Segment",
        "use_case": "Legal Functionality",
        "Legal Functionality – Main Category": "Legal Functionality",
        "Legal Functionality – Sub-Category": "Functionality Sub-Category",
        "AI Maturity Stage": "Maturity Entry Level",
        "AI Platform": "AI Platform Type",
        "Hosting Location / Data Residence": "Hosting Location",
        "Languages supported": "Languages Supported",
        "Main Problem Solved": "Main problem solved",
    }

    # Value normalization maps
    value_normalizations = {
        "AI Powered": {
            "True": "Yes",
            "true": "Yes",
            "False": "No",
            "false": "No",
        },
        "Maturity Entry Level": {
            "Enterprise": "Enterprise-grade",
            "Quick win": "Quick Win",
            "quick win": "Quick Win",
        },
        "Primary User Segment": {
            "Government agencies": "Government / Public Sector",
            "Government": "Government / Public Sector",
            "Govt": "Government / Public Sector",
        },
    }

    for k, v in model_obj.items():
        if k in SCHEMA_FIELDS:
            out[k] = coerce_value(k, v)

    for k, v in model_obj.items():
        lk = str(k).strip()
        if lk in synonyms:
            target = synonyms[lk]
            if target in SCHEMA_FIELDS and target not in out:
                out[target] = coerce_value(target, v)

    if "Regions Served" in out and isinstance(out["Regions Served"], str):
        out["Regions Served"] = [out["Regions Served"]]

    if "Legal Functionality" in out:
        out["Legal Functionality"] = canonicalize_main_category(
            out["Legal Functionality"]
        )
    if "Primary User Segment" in out:
        out["Primary User Segment"] = canonicalize_user_segments(out["Primary User Segment"])

    # Apply value normalizations
    for field, norm_map in value_normalizations.items():
        if field in out:
            val = out[field]
            if isinstance(val, str) and val in norm_map:
                out[field] = norm_map[val]
            elif isinstance(val, list):
                out[field] = [norm_map.get(v, v) for v in val]

    out = {k: v for k, v in out.items() if v not in ("", [], None)}
    return out

FALLBACK_MODELS = [
    OPENAI_MODEL,
    "gpt-4.1-mini",
    "o4-mini",
    "gpt-4o-mini",
]

def call_openai_json(system_msg: str, user_msg: str) -> Dict[str, Any]:
    last_err = None
    for m in FALLBACK_MODELS:
        try:
            resp = client.chat.completions.create(
                model=m,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content
            return json.loads(raw) if isinstance(raw, str) else raw
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            continue
    raise RuntimeError(f"All model attempts failed. Last error: {last_err}")

# =========================
# Routes
# =========================

# =========================
# Authentication Routes (Supabase)
# =========================

# Helper function for cookie settings
def get_cookie_secure():
    """Return True if running in production (HTTPS), False for development (HTTP)"""
    return os.getenv("ENVIRONMENT", "development") == "production"

@app.post("/auth/login")
async def login(req: LoginRequest, response: Response, request: Request):
    """Login endpoint - authenticates user via Supabase"""
    ip = get_client_ip(request)
    if not check_auth_rate_limit(ip, "login"):
        raise HTTPException(status_code=429, detail="Too many login attempts. Please wait before trying again.")
    if not check_login_lockout(ip, req.email):
        raise HTTPException(status_code=429, detail="Account temporarily locked due to repeated failures. Please try again later.")

    result = sign_in(req.email, req.password)

    if "error" in result:
        record_login_failure(ip, req.email)
        raise HTTPException(status_code=401, detail=result["error"])

    user = result["user"]
    session = result["session"]

    # Successful login — clear any recorded failures for this IP+email
    clear_login_failures(ip, req.email)

    # Set access token as HTTP-only cookie
    response.set_cookie(
        key="sb_access_token",
        value=session["access_token"],
        httponly=True,
        secure=get_cookie_secure(),
        samesite="lax",
        max_age=3600  # 1 hour (Supabase default)
    )

    # Set refresh token as HTTP-only cookie
    response.set_cookie(
        key="sb_refresh_token",
        value=session["refresh_token"],
        httponly=True,
        secure=get_cookie_secure(),
        samesite="lax",
        max_age=86400 * 7  # 7 days
    )

    return {
        "success": True,
        "user": {
            "email": user["email"],
            "role": user.get("role", "user")
        }
        # access_token intentionally omitted — delivered via HTTP-only cookie only
    }

@app.post("/auth/logout")
async def logout(
    response: Response,
    access_token: Optional[str] = Cookie(None, alias="sb_access_token")
):
    """Logout endpoint - clears session cookies"""
    if access_token:
        sign_out(access_token)

    response.delete_cookie(key="sb_access_token")
    response.delete_cookie(key="sb_refresh_token")

    return {"success": True}

@app.get("/auth/me")
async def get_me(user: Optional[dict] = Depends(get_current_user)):
    """Get current user info"""
    if not user:
        return {"authenticated": False}

    return {
        "authenticated": True,
        "user": {
            "email": user["email"],
            "role": user.get("role", "user"),
            "id": user.get("id")
        }
    }

@app.post("/auth/refresh")
async def refresh_token_endpoint(
    response: Response,
    request: Request,
    refresh_token: Optional[str] = Cookie(None, alias="sb_refresh_token")
):
    """Refresh access token using refresh token"""
    ip = get_client_ip(request)
    if not check_auth_rate_limit(ip, "refresh"):
        raise HTTPException(status_code=429, detail="Too many refresh attempts. Please wait before trying again.")

    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    result = refresh_session(refresh_token)

    if "error" in result:
        # Clear invalid cookies
        response.delete_cookie(key="sb_access_token")
        response.delete_cookie(key="sb_refresh_token")
        raise HTTPException(status_code=401, detail=result["error"])

    session = result["session"]

    # Update cookies with new tokens
    response.set_cookie(
        key="sb_access_token",
        value=session["access_token"],
        httponly=True,
        secure=get_cookie_secure(),
        samesite="lax",
        max_age=3600
    )

    response.set_cookie(
        key="sb_refresh_token",
        value=session["refresh_token"],
        httponly=True,
        secure=get_cookie_secure(),
        samesite="lax",
        max_age=86400 * 7
    )

    return {"success": True}

@app.post("/auth/exchange-token")
async def exchange_token_endpoint(req: Request, response: Response):
    """
    Exchange tokens from a Supabase email link (recovery/invite) for HTTP-only cookies.
    The frontend posts {access_token, refresh_token} from the URL hash so they never
    need to be stored in JS memory or sent as Authorization headers.
    """
    ip = get_client_ip(req)
    if not check_auth_rate_limit(ip, "exchange-token"):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait before trying again.")

    try:
        body = await req.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    access_token = body.get("access_token")
    refresh_token = body.get("refresh_token")

    if not access_token:
        raise HTTPException(status_code=400, detail="access_token required")

    user = get_user_from_token(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    response.set_cookie(
        key="sb_access_token",
        value=access_token,
        httponly=True,
        secure=get_cookie_secure(),
        samesite="lax",
        max_age=3600
    )
    if refresh_token:
        response.set_cookie(
            key="sb_refresh_token",
            value=refresh_token,
            httponly=True,
            secure=get_cookie_secure(),
            samesite="lax",
            max_age=86400 * 7
        )

    return {"success": True}

@app.post("/auth/forgot-password")
async def forgot_password(req: LoginRequest, request: Request):
    """Request password reset email"""
    ip = get_client_ip(request)
    if not check_auth_rate_limit(ip, "forgot-password"):
        raise HTTPException(status_code=429, detail="Too many reset requests. Please wait before trying again.")
    # Also throttle per email to prevent using different IPs to spam one address
    if not check_auth_rate_limit(req.email, "forgot-password"):
        raise HTTPException(status_code=429, detail="Too many reset requests. Please wait before trying again.")

    # Get the site URL for redirect - redirect to main page, frontend handles token
    site_url = os.getenv("SITE_URL", "https://legaltech-explorer.onrender.com")
    redirect_url = site_url.rstrip('/') + '/auth/callback'

    result = request_password_reset(req.email, redirect_url)

    # Always return success to prevent email enumeration
    return {"success": True, "message": "If an account exists, a reset email has been sent"}

@app.post("/auth/signup")
async def signup(req: SignUpRequest, request: Request):
    """Public sign-up — Supabase sends a verification email automatically"""
    ip = get_client_ip(request)
    if not check_auth_rate_limit(ip, "signup"):
        raise HTTPException(status_code=429, detail="Too many signup attempts. Please wait before trying again.")

    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    result = sign_up(
        req.email, req.password,
        first_name=req.first_name or "",
        last_name=req.last_name or "",
        company=req.company or "",
    )

    if "error" in result:
        error = result["error"]
        if "already registered" in error.lower() or "already exists" in error.lower():
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        raise HTTPException(status_code=400, detail=error)

    return {
        "success": True,
        "message": "Account created. Please check your email to verify your account before signing in."
    }


class ResendVerificationRequest(BaseModel):
    email: str

@app.post("/auth/resend-verification")
async def resend_verification_endpoint(req: ResendVerificationRequest, request: Request):
    """Resend email verification"""
    ip = get_client_ip(request)
    if not check_auth_rate_limit(ip, "resend-verification"):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait before trying again.")
    if not check_auth_rate_limit(req.email, "resend-verification"):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait before trying again.")

    result = resend_verification(req.email)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"success": True, "message": "Verification email resent. Please check your inbox."}


class UpdateProfileRequest(BaseModel):
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    company: Optional[str] = ""

@app.post("/auth/update-profile")
async def update_profile_endpoint(req: UpdateProfileRequest, user: dict = Depends(require_auth)):
    """Update the authenticated user's name and company in Supabase user_metadata."""
    result = update_user_profile(
        user["id"],
        first_name=req.first_name or "",
        last_name=req.last_name or "",
        company=req.company or "",
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"success": True}


class UpdatePasswordRequest(BaseModel):
    password: str

@app.post("/auth/update-password")
async def update_password_endpoint(
    req: UpdatePasswordRequest,
    request: Request,
    token: Optional[str] = Cookie(None, alias="sb_access_token")
):
    """Update user's password (requires valid recovery session via HTTP-only cookie)"""
    ip = get_client_ip(request)
    if not check_auth_rate_limit(ip, "update-password"):
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait before trying again.")

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    result = update_password(token, req.password)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return {"success": True, "message": "Password updated successfully"}

# =========================
# Admin Routes (User Management via Supabase)
# =========================
@app.post("/admin/invite")
async def create_invite_endpoint(req: InviteRequest, admin: dict = Depends(require_admin)):
    """Admin endpoint to send invite email via Supabase"""
    site_url = os.getenv("SITE_URL", "https://legaltech-explorer.onrender.com")

    result = admin_invite_user(
        email=req.email,
        role=req.role,
        redirect_url=site_url
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return {
        "success": True,
        "email": req.email,
        "message": "Invite email sent"
    }

@app.post("/admin/create-user")
async def create_user_endpoint(req: LoginRequest, admin: dict = Depends(require_admin)):
    """Admin endpoint to create user directly with password"""
    result = admin_create_user(
        email=req.email,
        password=req.password,
        role="user"
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return {
        "success": True,
        "user": result["user"]
    }

@app.get("/admin/users")
async def list_users_endpoint(admin: dict = Depends(require_admin)):
    """Admin endpoint to list all users with usage statistics"""
    users = get_all_users_stats()
    return {"users": users}

@app.get("/admin/users/{email}/stats")
async def get_user_stats_endpoint(email: str, admin: dict = Depends(require_admin)):
    """Admin endpoint to get detailed statistics for a specific user"""
    stats = get_user_stats(email)
    return stats

class UserStatusRequest(BaseModel):
    status: str  # 'active' or 'disabled'

@app.post("/admin/users/{email}/status")
async def set_user_status_endpoint(email: str, req: UserStatusRequest, admin: dict = Depends(require_admin)):
    """Admin endpoint to enable or disable a user account"""
    if req.status not in ['active', 'disabled']:
        raise HTTPException(status_code=400, detail="Status must be 'active' or 'disabled'")

    success = set_user_status(email, req.status)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")

    # Mirror the status to Supabase app_metadata so get_user_from_token
    # enforces it on every authenticated request, even with a live session
    sb_result = admin_set_user_status(email, req.status)
    if "error" in sb_result:
        print(f"[Auth] Warning: failed to sync status to Supabase for {email}: {sb_result['error']}")

    return {
        "success": True,
        "email": email,
        "status": req.status
    }

# =========================
# Public Routes
# =========================
@app.get("/")
async def root(user: Optional[dict] = Depends(get_current_user)):
    """Serve index.html - with optional authentication"""
    response = FileResponse("index.html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/login.html")
async def login_page():
    """Serve login page"""
    response = FileResponse("login.html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/terms")
async def terms_page():
    """Serve Terms of Use page"""
    response = FileResponse("terms.html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

@app.get("/auth/callback")
async def auth_callback():
    """Minimal auth callback page — no analytics, handles Supabase token exchange"""
    response = FileResponse("auth/callback.html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/merged_pref_top50.csv")
def serve_csv(user: dict = Depends(require_auth)):
    return FileResponse("merged_pref_top50.csv", media_type="text/csv")

@app.get("/merged_pref_top50_updated.csv")
def serve_updated_csv(user: dict = Depends(require_auth)):
    response = FileResponse("merged_pref_top50_updated.csv", media_type="text/csv")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/tools")
def get_tools(user: Optional[dict] = Depends(get_current_user)):
    """Return all legal tools from Supabase as JSON. Public endpoint — no auth required."""
    if not supabase_admin:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        response = supabase_admin.table("legal_tools").select("*").execute()
        # Strip embedding vectors (server-side only) and resolve logo URLs
        tools = []
        for t in response.data:
            tool = {k: v for k, v in t.items() if k != "embedding"}
            tool["__logo_url"] = get_logo_url(t.get("Vendor Name", ""))
            tools.append(tool)
        return JSONResponse(content={"tools": tools})
    except Exception as e:
        logger.error(f"[Tools] Failed to fetch tools from Supabase: {e}")
        raise HTTPException(status_code=500, detail="Failed to load tools")

@app.get("/health")
def health():
    return {"ok": True}


# =========================
# Report Generation
# =========================

# Build a lookup of vendor_name -> logo URL once at startup to avoid
# repeated filesystem scans on every /tools request
_LOGO_URL_CACHE: Dict[str, Optional[str]] = {}

def _build_logo_cache():
    """Walk the logos directory once and populate _LOGO_URL_CACHE."""
    if not os.path.isdir("logos"):
        return
    files = set(os.listdir("logos"))
    # Cache is populated on-demand per vendor but we pre-scan the dir
    # so os.path.exists calls are replaced by a set lookup
    _LOGO_URL_CACHE["__files__"] = files  # type: ignore

_build_logo_cache()

def get_logo_url(vendor_name: str) -> Optional[str]:
    """Return the URL path to the vendor logo if it exists on disk, or None."""
    if vendor_name in _LOGO_URL_CACHE:
        return _LOGO_URL_CACHE[vendor_name]
    files = _LOGO_URL_CACHE.get("__files__") or set()
    name_raw = re.sub(r'\s+', '', vendor_name)
    name_slug = re.sub(r'[^a-z0-9]', '', vendor_name.lower())
    result = None
    for name in [name_raw, name_slug]:
        for ext in ['png', 'jpg', 'jpeg', 'webp']:
            if f"{name}.{ext}" in files:
                result = f"/logos/{name}.{ext}"
                break
        if result:
            break
    _LOGO_URL_CACHE[vendor_name] = result
    return result


def get_logo_b64(vendor_name: str) -> Optional[str]:
    """Load a vendor logo from disk and return a base64 data URI, or None."""
    name_raw = re.sub(r'\s+', '', vendor_name)          # strip whitespace only
    name_slug = re.sub(r'[^a-z0-9]', '', vendor_name.lower())  # lowercase alphanumeric
    candidates = []
    for name in [name_raw, name_slug]:
        for ext in ['png', 'jpg', 'jpeg', 'webp']:
            candidates.append(f"logos/{name}.{ext}")
    for path in candidates:
        if os.path.exists(path):
            with open(path, 'rb') as f:
                data = base64.b64encode(f.read()).decode()
            ext = path.rsplit('.', 1)[-1]
            mime = 'image/jpeg' if ext in ('jpg', 'jpeg') else f'image/{ext}'
            return f"data:{mime};base64,{data}"
    return None


def clean_query_text(query: str) -> str:
    """Fix typos, capitalisation and grammar in a user search query for display in the report."""
    if not query or not query.strip():
        return query
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content":
                    "You are a copy editor. The user will give you a short search query. "
                    "Return ONLY the corrected query — fix any typos, spelling mistakes, and capitalisation errors, "
                    "and ensure it reads as natural English. Do not change the meaning or add extra words. "
                    "Do not add punctuation at the end. Return the corrected text only, no explanation."},
                {"role": "user", "content": query}
            ],
            temperature=0,
            max_tokens=100,
        )
        cleaned = resp.choices[0].message.content.strip().strip('"').strip("'")
        return cleaned if cleaned else query
    except Exception:
        return query


def get_structured_comparison(tools: List[Dict[str, Any]]) -> Dict:
    """Call OpenAI to produce per-tool analysis for the V3 report layout."""
    tool_summaries = ""
    for t in tools:
        name  = t.get('Product Name') or t.get('Vendor Name', '')
        desc  = (t.get('Product Description') or t.get('Vendor Overview', ''))[:300]
        func  = t.get('Legal Functionality', '')
        ai    = t.get('AI Powered', '')
        prob  = t.get('Main problem solved', '')
        mat   = t.get('Maturity Entry Level', '')
        tool_summaries += (
            f"\n**{name}**\n"
            f"- Description: {desc}\n"
            f"- Legal Functionality: {func}\n"
            f"- Main Problem Solved: {prob}\n"
            f"- AI Powered: {ai}\n"
            f"- AI Maturity: {mat}\n"
        )

    system_msg = (
        "You are an expert legal technology analyst writing a professional shortlist report for in-house legal teams. "
        "Analyze the provided legal tech tools and return a JSON object with one key \"tools\" containing an array of objects, "
        "one per tool in the SAME ORDER as provided. Each object must have exactly these keys:\n"
        "- \"name\": the tool's product name (string)\n"
        "- \"best_for\": a 3-6 word phrase describing the primary use case (e.g. 'Legal intake automation')\n"
        "- \"key_strength\": a 3-6 word phrase describing the standout strength (e.g. 'Strong workflow automation')\n"
        "- \"consideration\": a 3-8 word phrase describing the main limitation or trade-off (e.g. 'Narrower feature scope')\n"
        "- \"at_a_glance_blurb\": 1-2 sentences (max 30 words) describing when this tool is best suited. "
        "Start with 'Best suited where...', 'Most relevant where...' or 'Appropriate where...'\n"
        "- \"strengths\": 1-2 sentences describing the tool's primary strengths for in-house legal teams\n"
        "- \"weaknesses\": 1-2 sentences describing the main limitations or trade-offs buyers should consider\n"
        "- \"best_use_case\": 1-2 sentences describing the ideal team, organisation size, or scenario for this tool\n"
        "Write in a professional, authoritative tone suitable for senior legal counsel. "
        "Return ONLY valid JSON. No markdown, no code blocks, no prose outside the JSON."
    )
    user_msg = f"Analyze these legal tech tools:\n{tool_summaries}"

    try:
        result = call_openai_json(system_msg, user_msg)
        if 'tools' not in result or not isinstance(result['tools'], list):
            raise ValueError("Missing 'tools' array in AI response")
        return result
    except Exception as e:
        logger.error(f"[Report] Comparison AI call failed: {e}")
        fallback_tools = []
        for t in tools:
            name = t.get('Product Name') or t.get('Vendor Name', '')
            fallback_tools.append({
                "name": name,
                "best_for": "",
                "key_strength": "",
                "consideration": "",
                "at_a_glance_blurb": "",
                "strengths": "",
                "weaknesses": "",
                "best_use_case": "",
            })
        return {"tools": fallback_tools}


def merge_report_pdfs(dynamic_bytes: bytes) -> bytes:
    """Merge V3 static pages with dynamic pages into a 12-page PDF.

    Dynamic PDF page order (from report.html):
      d[0]  At a glance
      d[1]  Overview table
      d[2]  Tool 1 detail
      d[3]  Tool 2 detail
      d[4]  Tool 3 detail

    Final merged page order:
      1  Cover                  (static[0])
      2  About the Navigator    (static[1])
      3  At a glance            (dynamic[0])
      4  Key Considerations     (static[2])
      5  How to use this report (static[3])
      6  Section divider        (static[4])
      7  Overview table         (dynamic[1])
      8  Tool 1 detail          (dynamic[2])
      9  Tool 2 detail          (dynamic[3])
     10  Tool 3 detail          (dynamic[4])
     11  Next steps             (static[5])
     12  Back cover             (static[6])
    """
    from pypdf import PdfReader, PdfWriter
    writer = PdfWriter()
    static_path = "static/report_static_pages_v3.pdf"

    s = PdfReader(static_path)
    d = PdfReader(io.BytesIO(dynamic_bytes))

    writer.add_page(s.pages[0])   # 1  Cover (static)
    writer.add_page(s.pages[1])   # 2  About Navigator
    writer.add_page(d.pages[0])   # 3  At a glance
    writer.add_page(s.pages[2])   # 4  Key Considerations
    writer.add_page(s.pages[3])   # 5  How to use
    writer.add_page(s.pages[4])   # 6  Section divider
    for i in range(1, len(d.pages)):  # 7-10  Overview + tool detail pages
        writer.add_page(d.pages[i])
    writer.add_page(s.pages[5])   # 11 Next steps
    writer.add_page(s.pages[6])   # 12 Back cover

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


class ReportMeta(BaseModel):
    query: Optional[str] = ""
    generated_at: Optional[str] = ""

class ReportRequest(BaseModel):
    meta: ReportMeta = ReportMeta()
    tools: List[Dict[str, Any]] = []


@app.get("/report/preview", response_class=HTMLResponse)
async def report_preview(request: Request, user: dict = Depends(require_auth)):
    """Preview the report as HTML in the browser — for fast iteration during development."""
    # Phase 1: mock data only. Replace with real data in Phase 3.
    mock_tools = [
        {"Tool Name": "Acme Contract AI", "Vendor": "Acme Corp", "Category": "Contract Management",
         "Pricing": "Subscription", "Jurisdiction": "Australia", "Description": "AI-powered contract review and analysis platform for in-house legal teams."},
        {"Tool Name": "LexFlow", "Vendor": "LexFlow Pty Ltd", "Category": "Matter Management",
         "Pricing": "Per seat", "Jurisdiction": "Australia", "Description": "End-to-end matter and document management for corporate legal departments."},
        {"Tool Name": "ClauseCheck", "Vendor": "ClauseCheck Inc", "Category": "Due Diligence",
         "Pricing": "Freemium", "Jurisdiction": "Australia / NZ", "Description": "Automated clause extraction and risk flagging for M&A and compliance workflows."},
    ]
    mock_meta = {"query": "contract review tools for in-house team", "generated_at": "2026-03-03"}
    user_name = " ".join(filter(None, [user.get("first_name", ""), user.get("last_name", "")])).strip()
    return templates.TemplateResponse(
        "report.html",
        {
            "request": request,
            "tools": mock_tools,
            "meta": mock_meta,
            "user": user,
            "logos": [None, None, None],
            "comparison": {"tools": []},
            "user_name": user_name,
            "user_company": user.get("company", ""),
        }
    )


@app.post("/report")
async def generate_report(req: ReportRequest, user: dict = Depends(require_auth)):
    """Generate a 12-page PDF report: V3 static pages merged with 5 dynamic pages."""
    if not req.tools:
        raise HTTPException(status_code=400, detail="No tools provided")

    tools = req.tools[:3]
    today = datetime.date.today().isoformat()
    meta = {
        "query": clean_query_text(req.meta.query or ""),
        "generated_at": req.meta.generated_at or today,
    }

    # Extract personalisation from the authenticated user
    user_name = " ".join(filter(None, [
        user.get("first_name", ""), user.get("last_name", "")
    ])).strip()
    user_company = user.get("company", "")

    # Check cache — key scoped per user + tools + query so personalised covers don't collide
    tool_names = sorted(t.get('Vendor Name', '') for t in tools)
    report_cache_key = f"report:{user['id']}:{':'.join(tool_names)}:{meta['query']}"
    cached_pdf = cache_get(report_cache_key)
    if cached_pdf is not None:
        logger.info(f"[Cache] /report hit: {tool_names}")
        return StreamingResponse(
            iter([cached_pdf]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=Navigator-Snapshot-Report-{today}.pdf"}
        )

    # Load logos as base64 data URIs so Playwright doesn't need HTTP requests
    logos = [get_logo_b64(t.get('Vendor Name', '')) for t in tools]

    # Get structured AI comparison (4 sections)
    comparison = get_structured_comparison(tools)

    # Render dynamic pages (cover + at-a-glance + overview + tool detail pages)
    html = templates.get_template("report.html").render(
        request=None, tools=tools, meta=meta, logos=logos, comparison=comparison,
        user_name=user_name, user_company=user_company,
    )

    try:
        dynamic_pdf_bytes = await render_pdf(html, landscape=True)
    except Exception as e:
        logger.error(f"[Report] PDF render failed: {e}")
        raise HTTPException(status_code=500, detail="PDF generation failed. Please try again.")

    # Merge: static pages 1,2 + dynamic pages 3,4 + static page 5
    try:
        merged_bytes = merge_report_pdfs(dynamic_pdf_bytes)
    except Exception as e:
        logger.error(f"[Report] PDF merge failed: {e}")
        merged_bytes = dynamic_pdf_bytes

    cache_set(report_cache_key, merged_bytes, ttl=CACHE_TTL_REPORT)

    filename = f"Navigator-Snapshot-Report-{today}.pdf"
    return StreamingResponse(
        iter([merged_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

class SearchRequest(BaseModel):
    query: str
    limit: int = 25

@app.post("/search")
async def semantic_search(req: SearchRequest, user: dict = Depends(rate_limit_dependency)):
    """Semantic search using pgvector embeddings stored in Supabase."""
    if not supabase_admin:
        raise HTTPException(status_code=503, detail="Database not configured")

    try:
        log_usage(user['id'], user['email'], '/search', req.query)

        cache_key = f"search:{req.query.strip().lower()}:{req.limit}"
        cached = cache_get(cache_key)
        if cached is not None:
            logger.info(f"[Cache] /search hit: {req.query[:60]}")
            return cached

        # Embed the query
        embed_response = client.embeddings.create(
            model="text-embedding-3-small",
            input=req.query.strip()
        )
        query_vector = embed_response.data[0].embedding

        # Call pgvector RPC
        rpc_result = supabase_admin.rpc("match_tools", {
            "query_embedding": query_vector,
            "match_threshold": 0.45,
            "match_count": min(req.limit * 3, 100)
        }).execute()

        response_data = {
            "results": rpc_result.data,
            "query": req.query
        }
        cache_set(cache_key, response_data)
        return response_data

    except Exception as e:
        logger.error(f"[Search] Semantic search failed: {e}")
        raise HTTPException(status_code=500, detail="Search failed. Please try again.")


@app.post("/query")
async def generate_filters(req: Query, user: dict = Depends(rate_limit_dependency)):
    system_msg = (
        "You map natural-language legal-tech needs into structured filters for a database.\n"
        "Return ONLY a single JSON object (no markdown, no prose) using these EXACT field names when applicable:\n"
        f"{SCHEMA_FIELDS}\n\n"
        "Guidelines:\n"
        "- IMPORTANT: Do NOT set 'Regions Served' filter unless the user explicitly wants to filter BY region.\n"
        "  If the query mentions 'in Australia' or 'for Australian teams', this is just context, NOT a filter requirement.\n"
        "  Only set 'Regions Served' if the user says something like 'only Australian vendors' or 'must be based in Australia'.\n"
        "- For 'Legal Functionality', use ONE of these exact values:\n"
        "  * 'Contracting & Document Automation' (for contract automation, document automation, esignature, contract review)\n"
        "  * 'Matter, Workflow & Intake Management' (for matter management, workflow automation, intake)\n"
        "  * 'Legal Operations & Analytics' (for legal ops, analytics, reporting, ebilling)\n"
        "  * 'Outside Counsel & Spend Management' (ONLY for tools primarily focused on outside counsel management)\n"
        "  * 'Litigation, Disputes & Investigations' (for litigation, ediscovery, disputes)\n"
        "  * 'Knowledge, Search & Precedent Management' (for document management, knowledge management)\n"
        "  * 'Legal Research & Knowledge' (for legal research)\n"
        "  * 'AI Legal Assistants & Productivity Tools' (for AI assistants, copilots)\n"
        "  * 'Compliance, Risk & Governance' (for compliance, risk management)\n"
        "  * 'Intellectual Property, Technology & Data' (for patents, trademarks, IP portfolio, copyright)\n"
        "  * Other categories as applicable\n"
        "- For 'Primary User Segment', use ONE of: 'Corporate legal', 'Private practice', 'Legal Operations Professionals', etc.\n"
        "- IMPORTANT: For broad searches like 'spend management' or 'vendor management', use 'Legal Operations & Analytics' as the category\n"
        "  since most spend tools are in that category, NOT 'Outside Counsel & Spend Management'.\n"
        "- For 'AI Powered', use EXACTLY: 'Yes' or 'No' (NOT True/False)\n"
        "- For 'Deployment Model', use EXACTLY: 'Cloud (SaaS)' NOT 'Cloud-based'\n"
        "- For 'Maturity Entry Level', use ONE of: 'Enterprise-grade', 'Advanced', 'Quick Win', 'Experimental / early stage'\n"
        "- For 'Approx. Price Range (AUD)', use EXACTLY: '<$10K', '$10K–$50K', '$51K-$100K', or '$101K+'\n"
        "- For 'Ease of Purchase', use ONE of: 'Very Easy', 'Easy', 'Moderate', 'Complex'\n"
        "- For 'Primary User Segment' with government, use 'Government / Public Sector' NOT 'Government agencies'\n"
        "- Do NOT include 'Functionality Sub-Category' - focus on main category only.\n"
        "- Never invent vendor names or prices. Only filters.\n"
        "- If unsure about a field, omit it entirely.\n"
        "- Output JSON only, no explanations."
    )

    user_msg = f"User query:\n{req.query}\n\nReturn only the JSON object with filters."

    try:
        # Log the query
        log_usage(user['id'], user['email'], '/query', req.query)

        # Check cache first
        cache_key = f"query:{req.query.strip().lower()}"
        cached = cache_get(cache_key)
        if cached is not None:
            logger.info(f"[Cache] /query hit: {req.query[:60]}")
            return cached

        model_obj = call_openai_json(system_msg, user_msg)
        clean = normalize_to_schema(model_obj)
        cache_set(cache_key, clean)
        return clean
    except Exception as e:
        logger.error(f"[Query] Failed: {e}")
        return JSONResponse(status_code=500, content={"error": "Query processing failed. Please try again."})

@app.post("/summarize")
async def summarize_comparison(req: ComparisonRequest, user: dict = Depends(rate_limit_dependency)):
    """
    Generate an AI summary comparing multiple legal tech tools.
    """
    if not req.tools or len(req.tools) == 0:
        return JSONResponse(status_code=400, content={"error": "No tools provided for comparison"})

    # Build a comparison prompt
    tools_text = ""
    for i, tool in enumerate(req.tools, 1):
        tools_text += f"\n\n**Tool {i}: {tool.get('name', 'Unknown')}**\n"
        tools_text += f"- Vendor: {tool.get('vendor', 'N/A')}\n"
        tools_text += f"- Description: {tool.get('description', 'N/A')}\n"
        tools_text += f"- Pricing: {tool.get('pricing', 'N/A')}\n"
        tools_text += f"- Deployment: {tool.get('deployment', 'N/A')}\n"
        tools_text += f"- AI Powered: {tool.get('aiPowered', 'N/A')}\n"
        tools_text += f"- Ease of Purchase: {tool.get('easeOfPurchase', 'N/A')}\n"
        tools_text += f"- Adoption Level: {tool.get('adoptionLevel', 'N/A')}\n"

    system_msg = (
        "You are an expert legal technology consultant. Analyze the provided legal tech tools and generate "
        "a concise, insightful comparison summary. Focus on:\n"
        "1. Key similarities and differences\n"
        "2. Strengths and weaknesses of each tool\n"
        "3. Best use cases for each tool\n"
        "4. Pricing and value considerations\n"
        "5. A recommendation based on common use cases\n\n"
        "Format your response in clean HTML with paragraphs and bullet points. "
        "Keep it under 300 words and make it actionable for legal teams making purchasing decisions.\n"
        "Return ONLY a JSON object with a single 'summary' field containing the HTML content."
    )

    user_msg = f"Compare these legal tech tools:{tools_text}\n\nProvide a comparison summary in JSON format."

    try:
        # Log the comparison request
        tool_names = [t.get('name', 'Unknown') for t in req.tools]
        log_usage(user['id'], user['email'], '/summarize', f"Comparing: {', '.join(tool_names)}")

        # Check cache
        summarize_cache_key = f"summarize:{':'.join(sorted(tool_names))}"
        cached = cache_get(summarize_cache_key)
        if cached is not None:
            logger.info(f"[Cache] /summarize hit: {tool_names}")
            return cached

        result = call_openai_json(system_msg, user_msg)
        if isinstance(result, dict) and 'summary' in result:
            response = {"summary": result['summary']}
        else:
            response = {"summary": str(result)}

        cache_set(summarize_cache_key, response)
        return response
    except Exception as e:
        logger.error(f"[Summarize] Failed: {e}")
        return JSONResponse(status_code=500, content={"error": "Summary generation failed. Please try again."})
