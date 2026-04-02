"""
Search benchmark test harness.
Calls Supabase + OpenAI directly — no server needed.

Usage:
  python test_search.py          # new scoring
  python test_search.py --old    # old scoring (baseline comparison)
  python test_search.py --check  # check which expected tools are in Supabase at all
"""

import os, sys, re, csv
from dotenv import load_dotenv

load_dotenv(override=True)  # override=True forces .env to win over system env vars

try:
    from openai import OpenAI
    from supabase import create_client
except ImportError:
    print("Installing required packages...")
    os.system("pip install openai supabase python-dotenv -q")
    from openai import OpenAI
    from supabase import create_client

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL   = os.getenv("SUPABASE_URL")
SUPABASE_KEY   = os.getenv("SUPABASE_SERVICE_KEY")

oai      = OpenAI(api_key=OPENAI_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

USE_OLD_SCORING = "--old" in sys.argv
CHECK_DB        = "--check" in sys.argv

# ─── Load CSV for category enrichment (mirrors frontend DATA) ─────────────────
CSV_DATA = {}
try:
    with open("merged_pref_top50_updated.csv", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            key = (row.get("Vendor Name","").strip(), row.get("Product Name","").strip())
            CSV_DATA[key] = row
    print(f"Loaded {len(CSV_DATA)} tools from CSV for category enrichment.")
except FileNotFoundError:
    print("Warning: CSV not found — category data unavailable.")

def enrich(r):
    """Merge CSV fields into a Supabase result row (same as frontend DATA match)."""
    key = (r.get("Vendor Name","").strip(), r.get("Product Name","").strip())
    csv_row = CSV_DATA.get(key, {})
    return {**csv_row, **r}  # Supabase fields win for scores; CSV fills in metadata

# ─── Benchmark queries ────────────────────────────────────────────────────────
BENCHMARKS = [
    {
        "id":     "legal_ops",
        "query":  "Legal Operations Management SaaS platform for an in-house legal team",
        "expect": ["Xakia", "LawVue", "Lawcadia", "LawVu"],
        "reject": ["NetDocuments", "Adobe", "Agiloft"],
    },
    {
        "id":     "panel_rfp",
        "query":  "SaaS Platform for an inhouse team to manage a Legal Panel RFP",
        "expect": ["Persuit", "PERSUIT", "Lawcadia"],
        "reject": ["NetDocuments", "Adobe", "Agiloft"],
    },
    {
        "id":     "spend_billing",
        "query":  "SaaS Platform to manage legal spend, including automated ingestion of law firm invoices and assessment against billing guidelines",
        "expect": ["Brightflag"],
        "reject": ["NetDocuments", "Adobe", "Agiloft"],
    },
    {
        "id":     "tendering",
        "query":  "Platform to manage competitive tendering for legal engagements with legal panel",
        "expect": ["Lawcadia", "LawCadia", "Persuit", "PERSUIT"],
        "reject": ["NetDocuments", "Adobe", "Agiloft"],
    },
    {
        "id":     "ai_clm_hubspot",
        "query":  "AI-first CLM with the ability to extract data points from an existing population of buy-side and customer-side contracts. Must integrate with HubSpot CRM.",
        "expect": ["Juro", "Sirion", "ContractPodAI", "Ironclad", "Agiloft"],
        "reject": ["NetDocuments", "Adobe"],
    },
    {
        "id":     "kyc_hk",
        "query":  "Onboarding system for automated KYC and KYB inline with SFC requirements in Hong Kong",
        "expect": [],
        "reject": ["NetDocuments", "Adobe", "Agiloft"],
    },
]

# ─── Check which expected tools exist in Supabase ────────────────────────────
if CHECK_DB:
    print("\n=== DATABASE PRESENCE CHECK ===")
    all_targets = set()
    for b in BENCHMARKS:
        all_targets.update(b["expect"] + b["reject"])
    resp = supabase.table("legal_tools").select('"Vendor Name", "Product Name", popularity_score').execute()
    db_tools = {(r["Vendor Name"], r["Product Name"]) for r in (resp.data or [])}
    db_vendors = {r["Vendor Name"] for r in (resp.data or [])}
    for t in sorted(all_targets):
        found = any(t.lower() in v.lower() for v in db_vendors)
        status = "OK IN DB" if found else "XX MISSING"
        print(f"  {status}  {t}")
    print(f"\nTotal tools in Supabase: {len(db_tools)}")
    sys.exit(0)

# ─── Scoring logic ────────────────────────────────────────────────────────────
def detect_intent(q):
    q = q.lower()
    return {
        "dms":   bool(re.search(r'document management|dms|knowledge management|precedent|filing system', q)),
        "esign": bool(re.search(r'e-?sign|electronic sign|signature|signing', q)),
        "clm":   bool(re.search(r'\bclm\b|contract lifecycle|contract management|contract automation', q)),
        "spend": bool(re.search(r'spend|invoice|billing guideline|e-billing|ebilling', q)),
        "ops":   bool(re.search(r'legal ops|legal operations|operations management|matter management|intake', q)),
        "panel": bool(re.search(r'panel|rfp|\btendering\b|competitive tender|outside counsel', q)),
        "kyc":   bool(re.search(r'kyc|kyb|onboarding|aml|sfc|financial crime', q)),
    }

def category_penalty(tool, intent):
    if USE_OLD_SCORING:
        return 1.0
    cat    = (tool.get("Legal Functionality") or "").lower()
    subcat = (tool.get("Functionality Sub-Category") or "").lower()
    is_dms   = "knowledge, search" in cat
    is_esign = any(x in subcat for x in ["esignature", "e-sign", "pdf management"])
    is_clm   = "contract lifecycle management" in subcat

    if is_dms and not intent["dms"]:
        return 0.15
    if is_esign and not intent["esign"] and not intent["clm"]:
        return 0.10
    if is_clm and (intent["spend"] or intent["panel"]):
        return 0.20
    if is_clm and intent["ops"] and not intent["clm"]:
        return 0.40
    return 1.0

def blend(sim, pop_n, penalty):
    if USE_OLD_SCORING:
        return 0.65 * sim + 0.35 * pop_n
    return (0.85 * sim + 0.15 * pop_n) * penalty

# ─── Popularity normalisation ─────────────────────────────────────────────────
print("Fetching tool data from Supabase...")
all_resp = supabase.table("legal_tools").select('"Vendor Name", "Product Name", popularity_score').execute()
all_tools = all_resp.data or []
max_pop = max((float(t.get("popularity_score") or 0) for t in all_tools), default=1)
pop_map = {(t["Vendor Name"], t["Product Name"]): float(t.get("popularity_score") or 0)
           for t in all_tools}

# ─── Run benchmarks ───────────────────────────────────────────────────────────
mode = "OLD scoring (pre-fix)" if USE_OLD_SCORING else "NEW scoring (post-fix)"
print(f"\n{'='*72}")
print(f"  SEARCH BENCHMARK  —  {mode}")
print(f"{'='*72}\n")

total_pass = total_fail = 0

for bench in BENCHMARKS:
    q = bench["query"]
    print(f"[{bench['id'].upper()}]")
    print(f"  Query: {q[:85]}")

    vec = oai.embeddings.create(model="text-embedding-3-small", input=q).data[0].embedding

    threshold = 0.35 if USE_OLD_SCORING else 0.45
    raw = supabase.rpc("match_tools", {
        "query_embedding": vec,
        "match_threshold": threshold,
        "match_count": 30,
    }).execute().data or []

    if not raw:
        print("  !!  No results from Supabase\n")
        continue

    intent = detect_intent(q)
    scored = []
    for r in raw:
        r = enrich(r)
        sim   = float(r.get("similarity") or 0)
        pop   = pop_map.get((r.get("Vendor Name",""), r.get("Product Name","")), 0) / max_pop
        pen   = category_penalty(r, intent)
        final = blend(sim, pop, pen)
        scored.append({**r, "__final": final, "__sim": sim, "__pen": pen})

    scored.sort(key=lambda x: x["__final"], reverse=True)

    print(f"  {'#':<4} {'Score':>6}  {'Vendor':<22} {'Category':<30} {'Sub-cat':<25} {'Flag'}")
    print(f"  {'-'*105}")

    for i, r in enumerate(scored[:12], 1):
        vendor  = r.get("Vendor Name", "?")
        cat     = (r.get("Legal Functionality") or "?")[:28]
        subcat  = (r.get("Functionality Sub-Category") or "?")[:23]
        final   = r["__final"]
        sim     = r["__sim"]
        pen     = r["__pen"]

        is_exp = any(e.lower() in vendor.lower() for e in bench["expect"])
        is_rej = any(e.lower() in vendor.lower() for e in bench["reject"])
        flag   = "EXPECTED" if is_exp else ("WRONG" if is_rej else "")
        if is_exp: total_pass += 1
        if is_rej: total_fail += 1

        pen_str = f" pen={pen:.2f}" if pen < 1.0 else ""
        print(f"  #{i:<3} {final:>6.3f}  {vendor:<22} {cat:<30} {subcat:<25} {flag}{pen_str}")

    # Report expected tools outside top 12
    for e in bench["expect"]:
        in_top = any(e.lower() in r.get("Vendor Name","").lower() for r in scored[:12])
        if not in_top:
            rank = next((i+1 for i,r in enumerate(scored) if e.lower() in r.get("Vendor Name","").lower()), None)
            if rank:
                r = scored[rank-1]
                print(f"  !!  '{e}' at rank #{rank} — score {r['__final']:.3f} sim={r['__sim']:.3f} pen={r['__pen']:.2f}")
            else:
                print(f"  XX  '{e}' not in results (missing from DB or below threshold)")

    print(f"  Intent: {[k for k,v in intent.items() if v] or ['none']}\n")

print(f"{'='*72}")
print(f"  SUMMARY: {total_pass} expected tools in top 12 | {total_fail} wrong tools in top 12")
print(f"{'='*72}\n")
