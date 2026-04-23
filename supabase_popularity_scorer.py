"""
supabase_popularity_scorer.py
Calculates popularity_score for every tool in Supabase from existing
field values and writes it back. No external API calls — runs in seconds.

Formula (weights sum to 1.0):
    adoption_level    30%   Market Leader=100, Mainstream=75, Growing=50,
                             Emerging=25, otherwise 10
    maturity          20%   Enterprise-grade=100, Advanced=75, Quick Win=50,
                             Experimental=25
    google_trends     25%   raw score 0-100 from pytrends (stored in DB)
    ai_powered        10%   Yes=100, No=0
    regions_served     8%   number of regions × 20, capped at 100
    completeness       7%   fraction of key fields filled × 100

Usage:
    python supabase_popularity_scorer.py          # all tools
    python supabase_popularity_scorer.py --new    # only tools where popularity_score IS NULL
"""

import os, sys, argparse, requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
HEADERS      = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"}

WEIGHTS = {
    "adoption":    0.30,
    "maturity":    0.20,
    "trends":      0.25,
    "ai":          0.10,
    "regions":     0.08,
    "completeness":0.07,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 0.001

COMPLETENESS_FIELDS = [
    "Vendor Name", "Product Name", "Product Description", "Vendor Overview",
    "Legal Functionality", "Regions Served", "AI Powered",
    "Maturity Entry Level", "Adoption Level", "Vendor Website",
]


# ---------------------------------------------------------------------------
# Component scorers (all return 0-100)
# ---------------------------------------------------------------------------

def score_adoption(val: str | None) -> float:
    if not val:
        return 0.0
    v = str(val).strip()
    if "leader" in v.lower() or "standard" in v.lower():
        return 100.0
    if "mainstream" in v.lower() or "proven" in v.lower():
        return 75.0
    if "growing" in v.lower():
        return 50.0
    if "emerging" in v.lower() or "new entrant" in v.lower():
        return 25.0
    if "enterprise" in v.lower():   # "Enterprise-grade" listed under adoption for some rows
        return 75.0
    return 10.0


def score_maturity(val: str | None) -> float:
    if not val:
        return 0.0
    v = str(val).strip().lower()
    if "enterprise" in v:
        return 100.0
    if "advanced" in v:
        return 75.0
    if "quick win" in v:
        return 50.0
    if "experimental" in v or "early" in v:
        return 25.0
    return 0.0


def score_ai(val: str | None) -> float:
    return 100.0 if str(val or "").strip().lower() == "yes" else 0.0


def score_regions(val: str | None) -> float:
    if not val or str(val).strip() in ("", "nan"):
        return 0.0
    count = len([r for r in str(val).split(",") if r.strip()])
    return min(count * 20.0, 100.0)


def score_completeness(tool: dict) -> float:
    filled = sum(1 for f in COMPLETENESS_FIELDS
                 if tool.get(f) and str(tool[f]).strip() not in ("", "nan", "None"))
    return (filled / len(COMPLETENESS_FIELDS)) * 100.0


def calculate_popularity(tool: dict) -> float:
    trends_raw = tool.get("google_trends_score")
    trends = float(trends_raw) if trends_raw is not None else 0.0

    score = (
        score_adoption(tool.get("Adoption Level"))      * WEIGHTS["adoption"]
        + score_maturity(tool.get("Maturity Entry Level")) * WEIGHTS["maturity"]
        + trends                                          * WEIGHTS["trends"]
        + score_ai(tool.get("AI Powered"))               * WEIGHTS["ai"]
        + score_regions(tool.get("Regions Served"))      * WEIGHTS["regions"]
        + score_completeness(tool)                        * WEIGHTS["completeness"]
    )
    return round(score, 2)


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

FETCH_FIELDS = ",".join(f'"{f}"' for f in [
    "Vendor Name", "Product Name", "Adoption Level", "Maturity Entry Level",
    "AI Powered", "Regions Served", "google_trends_score", "popularity_score",
    "Product Description", "Vendor Overview", "Legal Functionality", "Vendor Website",
])


def fetch_tools(new_only: bool) -> list[dict]:
    params = f"select={FETCH_FIELDS}&limit=1000"
    if new_only:
        params += "&popularity_score=is.null"
    r = requests.get(f"{SUPABASE_URL}/rest/v1/legal_tools?{params}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def write_score(vendor: str, product: str, score: float) -> None:
    r = requests.patch(
        f'{SUPABASE_URL}/rest/v1/legal_tools'
        f'?{"Vendor Name"}=eq.{requests.utils.quote(vendor)}'
        f'&{"Product Name"}=eq.{requests.utils.quote(product)}',
        json={"popularity_score": score},
        headers=HEADERS,
    )
    r.raise_for_status()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--new", action="store_true",
                        help="Only score tools where popularity_score IS NULL")
    args = parser.parse_args()

    print("=" * 60)
    print("SUPABASE POPULARITY SCORER")
    print("=" * 60)

    tools = fetch_tools(new_only=args.new)
    total = len(tools)
    print(f"Tools to score: {total}\n")

    if total == 0:
        print("Nothing to do.")
        return

    scores = []
    errors = 0

    for i, tool in enumerate(tools, 1):
        vendor  = tool["Vendor Name"]
        product = tool.get("Product Name") or vendor
        score   = calculate_popularity(tool)

        try:
            write_score(vendor, product, score)
            scores.append(score)
            if i % 20 == 0 or i == total:
                print(f"  Progress: {i}/{total}", flush=True)
        except Exception as e:
            print(f"  ERROR {vendor}: {e!s:.80}")
            errors += 1

    if scores:
        avg = sum(scores) / len(scores)
        top5 = sorted(
            ((tool["Vendor Name"], calculate_popularity(tool)) for tool in tools),
            key=lambda x: x[1], reverse=True
        )[:5]

        print(f"\n{'='*60}")
        print(f"Done.  Scored: {len(scores)}  Errors: {errors}")
        print(f"Score range: {min(scores):.1f} – {max(scores):.1f}  |  Mean: {avg:.1f}")
        print(f"\nTop 5 by popularity:")
        for name, s in top5:
            print(f"  {s:5.1f}  {name}")


if __name__ == "__main__":
    main()
