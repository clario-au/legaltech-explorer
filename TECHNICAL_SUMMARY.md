# Legal-Tech Explorer - Technical Summary
**High-Level Overview for Consultants**

---

## What It Is

A web application that helps legal teams discover and evaluate legal technology vendors using AI-powered natural language search. Users can search in plain English (e.g., "contract automation for law firms") and get relevant, filtered results from a database of 431 legal tech products.

**Live:** https://legaltech-explorer.onrender.com
**Status:** Production-ready with authentication

---

## Tech Stack

```
Frontend:  Vanilla JavaScript (no framework)
Backend:   Python FastAPI
AI:        OpenAI GPT-4-mini
Database:  CSV file (main data) + SQLite (auth)
Hosting:   Render.com
```

**Why These Choices:**
- **Vanilla JS** - Simple, fast, no build step required
- **FastAPI** - Modern Python framework, great for APIs
- **CSV** - Quick to iterate, easy to update manually
- **SQLite** - Lightweight, serverless, perfect for small-scale auth

---

## Architecture Overview

### High-Level Data Flow

```
User Types Query
    ↓
Frontend sends to /query endpoint
    ↓
FastAPI Backend
    ↓
OpenAI GPT-4 translates to structured filters
    ↓
Frontend applies filters to CSV data
    ↓
Results displayed to user
```

### The Three Layers

#### 1. **Frontend Layer** (Browser)

**Single HTML file** with embedded JavaScript and CSS. No build tools, no bundlers.

**What it does:**
- Loads entire CSV database into memory on page load
- Renders dark-themed UI with search, filters, and results grid
- Sends natural language queries to backend
- Applies returned filters to local data
- Handles user authentication (login modal, session cookies)

**Key Features:**
- Real-time client-side filtering (instant results)
- Comparison tool (select multiple products, see side-by-side)
- Responsive design (works on desktop and mobile)
- Authentication-gated (login required to use)

**State Management:**
```javascript
window.APP_STATE = {
    allTools: [],        // All 431 products
    filteredTools: [],   // Current search results
    selectedTools: [],   // For comparison
    currentFilters: {}   // Active filters
}
```

#### 2. **Backend Layer** (Python FastAPI)

**Single Python file** that handles AI translation, authentication, and data serving.

**Core Endpoints:**

| Endpoint | What It Does |
|----------|--------------|
| `POST /query` | Takes natural language → Returns JSON filters |
| `POST /summarize` | Compares selected tools → Returns AI summary |
| `GET /merged_pref_top50_updated.csv` | Serves database file |
| `POST /auth/login` | Authenticates users |
| `GET /admin/users` | Admin dashboard (usage stats) |

**The AI Search Magic:**

```python
User Query: "contract automation for Australian law firms"

↓ Sent to OpenAI GPT-4 with 150+ line prompt ↓

GPT-4 Returns:
{
    "Legal Functionality": ["Contracting & Document Automation"],
    "Primary User Segment": ["Private practice"]
    // Note: Regions NOT filtered (smart interpretation)
}

↓ Frontend applies these filters ↓

Results: 23 matching tools
```

**Why This Works:**
- Detailed prompt engineering teaches GPT-4 the database schema
- Maps casual language to exact category names
- Understands legal tech domain terminology
- Validates output against schema before returning

**Security Features:**
- Session-based authentication (HTTP-only cookies)
- Bcrypt password hashing
- Rate limiting (20 requests per minute)
- Invite-only registration
- Usage logging for analytics

#### 3. **Data Layer**

**Two Databases:**

**Primary: CSV File** (`merged_pref_top50_updated.csv`)
- 431 tools × 31 fields
- Includes: vendor info, features, pricing, regions, certifications, popularity scores
- Loaded entirely into browser memory
- Updated manually (currently no automated pipeline)

**Authentication: SQLite** (`auth.db`)
- Tables: users, sessions, invites, usage_logs
- Stores hashed passwords, active sessions, usage analytics
- Small (~8KB base, grows with usage)

**Database Schema (Simplified):**
```
Tool Fields:
├── Identity: Vendor Name, Product Name, Description
├── Functionality: Legal Category, User Segment, Problem Solved
├── Technical: AI-Powered, Deployment Model, Hosting
├── Business: Pricing, Maturity Level, Adoption
└── Metrics: Popularity Score, Google Trends Score
```

---

## How It Was Built

### Development Journey

**Phase 1: Data Collection**
- Manually researched legal tech vendors
- Built web scraping tools (fetch_logos.py, collect_tool_data.py)
- Compiled CSV database with 31 standardized fields
- Added Google Trends popularity scoring

**Phase 2: Core Application**
- Built single-page frontend with vanilla JavaScript
- Implemented client-side filtering and sorting
- Added dark theme UI with glassmorphism effects
- Created comparison and detail views

**Phase 3: AI Search**
- Integrated OpenAI GPT-4 for natural language queries
- Engineered detailed prompts to map language → filters
- Added canonicalization for category matching
- Tested and refined with edge cases

**Phase 4: Authentication & Security**
- Added invite-only user system
- Implemented session-based authentication
- Built admin CLI tools for user management
- Added rate limiting and usage tracking

**Phase 5: Deployment**
- Deployed to Render.com (free tier)
- Set up auto-deploy from GitHub
- Configured environment variables
- Added monitoring and logging

---

## How It Works (End-to-End Example)

**User Journey:**

1. **User visits site** → Login modal appears (auth gate)
2. **User logs in** → Session cookie set, modal closes
3. **User types:** "I need a tool for Australian contract automation"
4. **Frontend sends** to `/query` endpoint
5. **Backend forwards** to OpenAI GPT-4 with detailed prompt
6. **GPT-4 analyzes** and returns structured filters:
   ```json
   {
     "Legal Functionality": ["Contracting & Document Automation"],
     "Primary User Segment": ["Private practice", "Corporate legal"]
   }
   ```
7. **Frontend receives** filters and applies to local CSV data
8. **Results displayed** in grid (e.g., 23 matching tools)
9. **User can:**
   - Sort results by any column
   - View detailed info for each tool
   - Select multiple tools for comparison
   - Apply additional manual filters
10. **All activity logged** to usage_logs table for analytics

---

## Current State & Limitations

### What Works Well ✅

- **Natural language search** - Intuitive, accurate 80% of the time
- **Fast filtering** - Instant results (all data client-side)
- **Secure authentication** - Industry-standard bcrypt + sessions
- **Usage analytics** - Full tracking of who searches what
- **Admin tools** - CLI for user management and stats

### Known Issues ⚠️

**Backend Architecture:**
- CSV database won't scale beyond ~1,000 tools
- No caching = expensive OpenAI costs
- In-memory rate limiting resets on server restart
- No database versioning or migrations

**AI Search Quality:**
- Sometimes picks wrong category for ambiguous queries
- Can't handle complex compound queries ("X OR Y")
- No learning from user feedback
- Region filtering can be confused (context vs filter)

**Data Quality:**
- 40-80% missing data in some fields (certifications, pricing, etc.)
- No automated data collection pipeline
- Manual updates only
- No vendor verification process

**Infrastructure:**
- Free tier sleeps after 15min → slow first load
- Single server instance (no scaling)
- No error monitoring or alerting
- No backup strategy

---

## Improvement Priorities

### 🔴 Critical (Do First)

**1. Migrate to PostgreSQL**
- Current CSV approach won't scale
- Need proper indexing, full-text search
- Enable database migrations and versioning

**2. Add Redis Caching**
- Cache OpenAI responses (reduce costs 60-70%)
- Move rate limiting to Redis (persist across restarts)
- Store sessions in Redis (better performance)

**3. Improve AI Search**
- Add semantic similarity (vector embeddings)
- Implement query classification
- Better handling of compound queries
- Add user feedback loop

### 🟡 Medium (Soon)

**4. Data Quality Pipeline**
- Automate web scraping for missing data
- Vendor verification emails
- User contribution system with approval workflow

**5. Monitoring & Analytics**
- Add Sentry for error tracking
- Implement usage dashboards
- Track OpenAI costs
- Set up uptime monitoring

### 🟢 Low (Eventually)

**6. Frontend Polish**
- Virtual scrolling for performance
- Better mobile experience
- Accessibility improvements
- Enhanced visualizations

---

## Specific Help Needed from Consultants

### Backend Engineers
- Design PostgreSQL schema and migration path
- Implement Redis caching strategy
- Set up proper CI/CD pipeline
- Add API versioning and documentation

### ML/NLP Engineers
- Improve AI prompt engineering (test Claude, Gemini)
- Add vector embeddings for semantic search
- Build query classification system
- Implement ranking algorithm

### Data Engineers
- Automate web scraping for data collection
- Clean and validate existing data
- Build vendor portal for self-service updates
- Set up data quality monitoring

### Frontend Developers
- Optimize performance (virtual scrolling, lazy loading)
- Improve mobile UX
- Add accessibility features
- Build admin dashboard UI

### DevOps
- Set up production-grade deployment (Docker, K8s)
- Implement monitoring and alerting
- Create staging environment
- Set up database backups

---

## Quick Start for Development

```bash
# 1. Clone and setup
git clone https://github.com/uptown-shrimp/legaltech-explorer.git
cd legaltech-explorer/database_ui
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
echo "OPENAI_API_KEY=your_key" > .env

# 3. Initialize
python -c "from auth_models import init_db; init_db()"
python admin_cli.py create-admin admin@test.com password123

# 4. Run
uvicorn ai_search_api:app --reload --port 8000

# 5. Visit http://localhost:8000
```

---

## Key Metrics

**Current Scale:**
- 431 legal tech products
- 31 data fields per product
- ~13,000 total data points
- Average query cost: $0.0002
- Response time: ~2 seconds (AI query)
- Filter time: ~50ms (client-side)

**Usage (Production):**
- Monthly OpenAI cost: $50-100 (depends on usage)
- Hosting: Free tier Render
- Database size: 400KB (CSV) + 8KB (SQLite base)

---

## Resources

**Production:** https://legaltech-explorer.onrender.com
**GitHub:** https://github.com/uptown-shrimp/legaltech-explorer
**Docs:** See USAGE_TRACKING_README.md, AUTH_README.md

**Getting Started:**
1. Request invite from admin
2. Register with @clario.com.au email
3. Login and explore
4. Review code and pick improvement area
5. Submit PRs via GitHub

---

**Version:** 0.2.0
**Last Updated:** February 2026
**Maintainer:** Clario Legal Tech Team
