# Authentication System - Technical Breakdown

---

## Overview

The Legal-Tech Explorer uses a **session-based authentication system** with server-side session storage in SQLite. This is a traditional, secure approach (not JWT-based).

**Key Philosophy:**
- Server maintains session state
- Client only holds session cookie
- No sensitive data in browser localStorage or cookies (except session ID)

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         USER FLOW                            │
└─────────────────────────────────────────────────────────────┘

Registration (Invite-Based):
Admin → Creates Invite → Token Generated → Email Sent
                                ↓
User Clicks Link → Frontend Shows Modal → User Sets Password
                                ↓
Password Hashed (bcrypt) → User Created → Session Created
                                ↓
HTTP-only Cookie Set → User Logged In


Login (Email/Password):
User Submits Credentials → Backend Verifies → Session Created
                                ↓
HTTP-only Cookie Set → User Logged In


Authentication Check (Every Request):
Request Includes Cookie → Backend Reads session_id
                                ↓
Validates Session → Checks Expiry → Loads User
                                ↓
Request Proceeds (or 401 Unauthorized)
```

---

## Database Schema

### Tables in `auth.db`

```sql
-- 1. Users Table
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,              -- User identifier
    password_hash TEXT NOT NULL,             -- Bcrypt hash (never plain text)
    role TEXT DEFAULT 'user',                -- 'user' or 'admin'
    client_id TEXT,                          -- Optional: for multi-tenant
    status TEXT DEFAULT 'active',            -- 'active' or 'disabled'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP                     -- Updated on each login
);

-- 2. Sessions Table
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,         -- Random 256-bit token
    user_id INTEGER NOT NULL,                -- FK to users.id
    expires_at TIMESTAMP NOT NULL,           -- UTC timestamp
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 3. Invites Table
CREATE TABLE invites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT UNIQUE NOT NULL,              -- Random 256-bit token
    email TEXT NOT NULL,                     -- Pre-assigned email
    role TEXT DEFAULT 'user',                -- Role to assign on registration
    client_id TEXT,                          -- Optional
    expires_at TIMESTAMP NOT NULL,           -- UTC timestamp (72 hours)
    used BOOLEAN DEFAULT 0,                  -- Prevents reuse
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    used_at TIMESTAMP                        -- When user registered
);

-- 4. Usage Logs Table
CREATE TABLE usage_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    user_email TEXT NOT NULL,                -- Denormalized for faster queries
    endpoint TEXT NOT NULL,                  -- '/query' or '/summarize'
    query_text TEXT,                         -- User's search query (nullable)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

**Indexes (Implicit):**
- PRIMARY KEY on `id` fields (auto-indexed)
- UNIQUE on `email`, `session_id`, `token` (auto-indexed)

**No Explicit Indexes Yet** - Opportunity for optimization on:
- `sessions.user_id`
- `sessions.expires_at`
- `usage_logs.user_id`
- `usage_logs.created_at`

---

## Password Security

### Hashing Algorithm: bcrypt

**Implementation:**
```python
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

# Hash password (on registration/password change)
password_hash = pwd_context.hash(plaintext_password)
# Example output: "$2b$12$KIXxBV..."

# Verify password (on login)
is_valid = pwd_context.verify(plaintext_password, stored_hash)
```

**Security Properties:**
- **Salt:** Automatically generated and embedded in hash
- **Cost Factor:** 12 rounds (2^12 iterations) - industry standard
- **One-way:** Cannot be reversed (only verify)
- **Adaptive:** Can increase cost factor as hardware improves

**Why bcrypt:**
- Designed for password hashing (unlike SHA-256)
- Built-in salt prevents rainbow table attacks
- Slow by design (prevents brute force)
- Battle-tested since 1999

**Bcrypt Version:**
```python
# requirements.txt
bcrypt==4.1.2  # Not 5.0.0 (compatibility issue with passlib)
passlib==1.7.4
```

**Password Storage Rules:**
1. **Never store plaintext** - Only hash is stored
2. **Never log passwords** - Not in logs, not in error messages
3. **Hash on server** - Never send hash from client
4. **One hash per user** - No shared hashes

---

## Session Management

### Session Creation

**When:** After successful login or registration

**Process:**
```python
import secrets
from datetime import datetime, timedelta

def create_session(user_id: int, expires_hours: int = 24) -> str:
    # 1. Generate cryptographically secure random token
    session_id = secrets.token_urlsafe(32)  # 256 bits of entropy
    # Example: "k3j5h6g7f8d9s0a1b2c3d4e5f6g7h8i9"

    # 2. Calculate expiration (24 hours from now)
    expires_at = datetime.utcnow() + timedelta(hours=expires_hours)

    # 3. Store in database
    cursor.execute("""
        INSERT INTO sessions (session_id, user_id, expires_at)
        VALUES (?, ?, ?)
    """, (session_id, user_id, expires_at.isoformat()))

    # 4. Return session_id (will be set as cookie)
    return session_id
```

**Token Generation:**
- Uses Python's `secrets` module (CSPRNG)
- `token_urlsafe(32)` = 32 bytes = 256 bits
- URL-safe base64 encoding (safe for cookies)
- Collision probability: negligible (2^256 possibilities)

### Session Cookies

**Set Cookie Response:**
```python
from fastapi import Response

def set_session_cookie(response: Response, session_id: str):
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,              # Prevents JavaScript access (XSS protection)
        secure=is_production(),     # HTTPS-only in production
        samesite="lax",             # CSRF protection
        max_age=86400,              # 24 hours (in seconds)
        path="/"                    # Cookie sent on all paths
    )
```

**Cookie Attributes Explained:**

| Attribute | Value | Purpose |
|-----------|-------|---------|
| `httponly=True` | JavaScript cannot access | Prevents XSS attacks from stealing session |
| `secure=True` (prod) | HTTPS-only | Prevents man-in-the-middle attacks |
| `samesite="lax"` | Sent on same-site requests | Prevents CSRF attacks |
| `max_age=86400` | 24 hours | Auto-expires in browser |
| `path="/"` | All paths | Cookie sent on every request |

**Environment-Based Security:**
```python
def get_cookie_secure() -> bool:
    # Development (HTTP): secure=False
    # Production (HTTPS): secure=True
    return os.getenv("ENVIRONMENT", "development") == "production"
```

### Session Validation

**On Every Protected Request:**
```python
async def get_current_user(session_id: Optional[str] = Cookie(None)):
    # 1. Check if cookie exists
    if not session_id:
        return None  # Not logged in

    # 2. Look up session in database
    cursor.execute(
        "SELECT * FROM sessions WHERE session_id = ?",
        (session_id,)
    )
    session = cursor.fetchone()

    if not session:
        return None  # Invalid session

    # 3. Check expiration
    expires_at = datetime.fromisoformat(session['expires_at'])
    if datetime.utcnow() > expires_at:
        return None  # Expired session

    # 4. Load user
    cursor.execute(
        "SELECT * FROM users WHERE id = ?",
        (session['user_id'],)
    )
    user = cursor.fetchone()

    # 5. Check user status
    if not user or user['status'] != 'active':
        return None  # User disabled or deleted

    # 6. Return user object
    return dict(user)
```

**FastAPI Dependency:**
```python
# Public endpoint (optional auth)
@app.get("/")
async def root(user: Optional[dict] = Depends(get_current_user)):
    # user is None if not logged in
    # user is dict if logged in

# Protected endpoint (required auth)
async def require_auth(user: Optional[dict] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

@app.post("/query")
async def search(user: dict = Depends(require_auth)):
    # user is guaranteed to exist here
```

### Session Lifecycle

```
Create Session:
├── User logs in successfully
├── Generate random session_id (256-bit)
├── Store in sessions table with 24hr expiry
├── Set HTTP-only cookie in response
└── Browser stores cookie

Validate Session (every request):
├── Browser automatically sends cookie
├── Backend extracts session_id
├── Look up in sessions table
├── Check expiration
├── Load user from users table
└── Attach user to request

Expire Session:
├── Automatic: 24 hours after creation
├── Manual: User clicks logout
├── Cleanup: Cron job deletes expired sessions
└── Browser deletes cookie (max_age reached)
```

**Session Cleanup:**
```python
def cleanup_expired_sessions():
    """Remove expired sessions from database"""
    cursor.execute("""
        DELETE FROM sessions
        WHERE expires_at < ?
    """, (datetime.utcnow().isoformat(),))
    conn.commit()

# Should be run periodically (currently manual)
# TODO: Add scheduled job (celery, cron, etc.)
```

---

## User Registration Flow

### Invite-Based System

**Why Invite-Only:**
- Prevents spam/abuse
- Controls who can access
- Pre-assigns email addresses
- Can set role before registration

### Step-by-Step Process

**1. Admin Creates Invite**

```python
def create_invite(email: str, role: str = "user", expires_hours: int = 72) -> str:
    # Generate token
    token = secrets.token_urlsafe(32)  # 256-bit random string

    # Calculate expiration (72 hours)
    expires_at = datetime.utcnow() + timedelta(hours=expires_hours)

    # Store invite
    cursor.execute("""
        INSERT INTO invites (token, email, role, expires_at)
        VALUES (?, ?, ?, ?)
    """, (token, email, role, expires_at.isoformat()))

    conn.commit()

    return token  # Admin sends this to user
```

**CLI Command:**
```bash
python admin_cli.py create-invite user@example.com

# Output:
# ✓ Invite created successfully!
#   Email: user@example.com
#   Role: user
#   Token: k3j5h6g7f8d9s0a1b2c3d4e5f6g7h8i9
#   Invite URL:
#   https://legaltech-explorer.onrender.com/register?token=k3j5h6g7...
#   This invite will expire in 72 hours.
```

**2. User Receives Invite Link**

```
https://legaltech-explorer.onrender.com/register?token=k3j5h6g7f8d9s0a1b2c3d4e5f6g7h8i9
```

**3. Frontend Validates Token**

```javascript
// On page load, check for ?token= in URL
const urlParams = new URLSearchParams(window.location.search);
const token = urlParams.get('token');

if (token) {
    // Validate invite
    const response = await fetch(`/auth/check-invite/${token}`);
    const data = await response.json();

    if (data.valid) {
        // Show registration modal with pre-filled email
        openRegisterModal(data.email, token);
    } else {
        alert('Invalid or expired invite link');
    }
}
```

**Backend Validation:**
```python
@app.get("/auth/check-invite/{token}")
async def check_invite(token: str):
    invite = get_invite(token)

    if not invite:
        return {"valid": False, "error": "Invite not found"}

    if invite['used']:
        return {"valid": False, "error": "Invite already used"}

    expires_at = datetime.fromisoformat(invite['expires_at'])
    if datetime.utcnow() > expires_at:
        return {"valid": False, "error": "Invite expired"}

    return {
        "valid": True,
        "email": invite['email'],
        "role": invite['role']
    }
```

**4. User Sets Password**

```javascript
// Registration form submission
const formData = {
    token: token,
    password: password  // User-entered password
};

const response = await fetch('/auth/register', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(formData)
});
```

**Backend Registration:**
```python
@app.post("/auth/register")
async def register(req: RegisterRequest, response: Response):
    # 1. Validate invite
    invite = validate_invite(req.token)
    if not invite:
        raise HTTPException(status_code=400, detail="Invalid invite")

    # 2. Check if user already exists
    existing = get_user_by_email(invite['email'])
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    # 3. Hash password
    password_hash = hash_password(req.password)

    # 4. Create user
    user_id = create_user(
        email=invite['email'],
        password=req.password,  # Will be hashed inside create_user
        role=invite['role']
    )

    # 5. Mark invite as used
    mark_invite_used(req.token)

    # 6. Create session (auto-login)
    session_id = create_session(user_id)

    # 7. Set cookie
    set_session_cookie(response, session_id)

    # 8. Return user info
    user = get_user_by_id(user_id)
    return {"user": user}
```

**5. Invite Marked as Used**

```python
def mark_invite_used(token: str):
    cursor.execute("""
        UPDATE invites
        SET used = 1, used_at = CURRENT_TIMESTAMP
        WHERE token = ?
    """, (token,))
    conn.commit()
```

**Security Properties:**
- Token can only be used once
- Token expires after 72 hours
- Email is pre-assigned (can't register with different email)
- Role is pre-determined
- Token is cryptographically random

---

## Login Flow

**1. User Submits Credentials**

```javascript
// Frontend
const formData = {
    email: email,
    password: password
};

const response = await fetch('/auth/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(formData)
});
```

**2. Backend Validates**

```python
@app.post("/auth/login")
async def login(req: LoginRequest, response: Response):
    # 1. Look up user by email
    user = get_user_by_email(req.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # 2. Check account status
    if user['status'] != 'active':
        raise HTTPException(status_code=403, detail="Account disabled")

    # 3. Verify password
    is_valid = verify_password(req.password, user['password_hash'])
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # 4. Update last login timestamp
    update_last_login(user['id'])

    # 5. Create new session
    session_id = create_session(user['id'])

    # 6. Set cookie
    set_session_cookie(response, session_id)

    # 7. Return user info (without password_hash)
    safe_user = {k: v for k, v in user.items() if k != 'password_hash'}
    return {"user": safe_user}
```

**Password Verification:**
```python
def verify_password(plaintext: str, hash: str) -> bool:
    """
    Compares plaintext password against bcrypt hash.
    Uses constant-time comparison to prevent timing attacks.
    """
    return pwd_context.verify(plaintext, hash)
```

**Security Notes:**
- Same error message for "user not found" and "wrong password" (prevents user enumeration)
- Password verification is constant-time (prevents timing attacks)
- Failed login attempts are not currently tracked (TODO: add brute force protection)

---

## Logout Flow

**1. User Clicks Logout**

```javascript
async function logout() {
    await fetch('/auth/logout', {method: 'POST'});
    window.location.href = '/';  // Redirect to home
}
```

**2. Backend Deletes Session**

```python
@app.post("/auth/logout")
async def logout(
    response: Response,
    session_id: Optional[str] = Cookie(None)
):
    if session_id:
        # Delete session from database
        delete_session(session_id)

    # Clear cookie
    response.delete_cookie(
        key="session_id",
        path="/"
    )

    return {"success": True}
```

**Delete Session:**
```python
def delete_session(session_id: str):
    cursor.execute(
        "DELETE FROM sessions WHERE session_id = ?",
        (session_id,)
    )
    conn.commit()
```

---

## Direct User Creation (No Invite)

**For Quick Onboarding:**

```bash
# Create admin
python admin_cli.py create-admin admin@example.com SecurePass123

# Create regular user
python admin_cli.py create-user user@example.com Password456
```

**Implementation:**
```python
def create_user(email: str, password: str, role: str = "user") -> int:
    # 1. Check if user exists
    existing = get_user_by_email(email)
    if existing:
        return None  # Already exists

    # 2. Hash password
    password_hash = pwd_context.hash(password)

    # 3. Insert user
    cursor.execute("""
        INSERT INTO users (email, password_hash, role)
        VALUES (?, ?, ?)
    """, (email, password_hash, role))

    # 4. Return user ID
    user_id = cursor.lastrowid
    conn.commit()

    return user_id
```

**Difference from Invite Flow:**
- No invite token required
- User can login immediately
- Password set by admin (should be changed by user)

---

## Authorization (Role-Based Access)

**Two Roles:**
- `user` - Regular users (consultants)
- `admin` - Administrators

**Admin-Only Endpoints:**
```python
async def require_admin(user: dict = Depends(require_auth)):
    """Dependency that requires admin role"""
    if user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

@app.post("/admin/invite")
async def create_invite_endpoint(req: InviteRequest, admin: dict = Depends(require_admin)):
    # Only admins can create invites
    ...

@app.get("/admin/users")
async def list_users(admin: dict = Depends(require_admin)):
    # Only admins can view user list
    ...
```

**Access Control Matrix:**

| Endpoint | Anonymous | User | Admin |
|----------|-----------|------|-------|
| `GET /` | ✅ | ✅ | ✅ |
| `GET /health` | ✅ | ✅ | ✅ |
| `POST /auth/login` | ✅ | ✅ | ✅ |
| `POST /auth/register` | ✅ | ✅ | ✅ |
| `GET /auth/me` | ✅ | ✅ | ✅ |
| `POST /query` | ❌ | ✅ | ✅ |
| `POST /summarize` | ❌ | ✅ | ✅ |
| `GET /merged_pref_top50_updated.csv` | ❌ | ✅ | ✅ |
| `POST /admin/invite` | ❌ | ❌ | ✅ |
| `GET /admin/users` | ❌ | ❌ | ✅ |
| `POST /admin/users/{email}/status` | ❌ | ❌ | ✅ |

---

## Usage Tracking

**Automatic Logging:**
```python
@app.post("/query")
async def generate_filters(req: Query, user: dict = Depends(rate_limit_dependency)):
    # Log the query
    log_usage(user['id'], user['email'], '/query', req.query)

    # ... rest of endpoint logic
```

**Log Function:**
```python
def log_usage(user_id: int, user_email: str, endpoint: str, query_text: Optional[str] = None):
    cursor.execute("""
        INSERT INTO usage_logs (user_id, user_email, endpoint, query_text)
        VALUES (?, ?, ?, ?)
    """, (user_id, user_email, endpoint, query_text))
    conn.commit()
```

**Logged Data:**
- User ID and email
- Endpoint called (`/query` or `/summarize`)
- Query text (for `/query`)
- Timestamp (automatic)

**Usage Analytics:**
```bash
# View all users with request counts
python usage_cli.py list

# View specific user's activity
python usage_cli.py stats user@example.com
```

---

## Security Considerations

### ✅ What's Secure

1. **Password Storage**
   - Bcrypt hashing with salt
   - Cost factor 12 (industry standard)
   - Passwords never logged or exposed

2. **Session Management**
   - HTTP-only cookies (XSS protection)
   - Secure flag in production (HTTPS-only)
   - SameSite attribute (CSRF protection)
   - 24-hour expiration
   - Server-side validation

3. **Invite System**
   - Cryptographically random tokens
   - One-time use
   - Time-limited (72 hours)
   - Pre-assigned emails

4. **Access Control**
   - Role-based authorization
   - Session validation on every request
   - User status checking (active/disabled)

### ⚠️ Potential Improvements

1. **Rate Limiting Login Attempts**
   - Currently: No protection against brute force
   - Recommendation: Add rate limiting to `/auth/login`

2. **Password Requirements**
   - Currently: Minimum 8 characters (frontend only)
   - Recommendation: Enforce complexity on backend

3. **Session Cleanup**
   - Currently: Manual cleanup of expired sessions
   - Recommendation: Scheduled job (cron, celery)

4. **Account Lockout**
   - Currently: No lockout after failed attempts
   - Recommendation: Temporary lock after 5 failed logins

5. **Two-Factor Authentication**
   - Currently: Not implemented
   - Recommendation: Optional TOTP for admin accounts

6. **Password Reset**
   - Currently: Must ask admin to reset
   - Recommendation: Self-service password reset via email

7. **Audit Logging**
   - Currently: Only API usage logged
   - Recommendation: Log all auth events (login, logout, password changes)

---

## Key Files

```
auth_models.py           # Core auth logic (DB operations)
ai_search_api.py         # FastAPI endpoints (routes)
admin_cli.py             # CLI for user management
usage_cli.py             # CLI for usage analytics
auth_ui.html             # Frontend auth UI (modals)
login.html               # Standalone login page
auth.db                  # SQLite database
```

---

## Common Operations

### Create Admin User
```bash
python admin_cli.py create-admin admin@example.com Password123
```

### Create Regular User
```bash
python admin_cli.py create-user user@example.com Password123
```

### Create Invite
```bash
python admin_cli.py create-invite user@example.com
# Returns: https://legaltech-explorer.onrender.com/register?token=...
```

### Disable User
```bash
python usage_cli.py disable user@example.com
```

### Enable User
```bash
python usage_cli.py enable user@example.com
```

### View User Stats
```bash
python usage_cli.py stats user@example.com
```

### View All Users
```bash
python usage_cli.py list
```

---

## Summary

**Architecture:** Session-based authentication with SQLite storage

**Key Components:**
- Bcrypt password hashing
- HTTP-only session cookies
- Invite-based registration
- Role-based authorization
- Usage tracking

**Security Posture:** Good for small-scale production, room for improvement at scale

**Next Steps:**
- Add brute force protection
- Implement password reset
- Schedule session cleanup
- Consider Redis for sessions (better performance)
