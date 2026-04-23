"""
supabase_trends_scorer.py
Fetches tools from Supabase where google_trends_score IS NULL,
queries Google Trends for each, and writes the score back.

Usage:
    python supabase_trends_scorer.py              # only NULL scores
    python supabase_trends_scorer.py --all        # re-score every tool
    python supabase_trends_scorer.py --limit 20   # first N unscored only
"""

import os, sys, time, random, argparse, requests
from dotenv import load_dotenv

try:
    from pytrends.request import TrendReq
except ImportError:
    raise SystemExit("Run: pip install pytrends")

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
HEADERS      = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"}

MIN_DELAY    = 5.0   # seconds between requests
MAX_RETRIES  = 3
MAX_429      = 5     # hard stop after this many rate-limit errors


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def fetch_tools(unscored_only: bool) -> list[dict]:
    params = 'select="Vendor Name","Product Name",google_trends_score&limit=1000'
    if unscored_only:
        params += "&google_trends_score=is.null"
    r = requests.get(f"{SUPABASE_URL}/rest/v1/legal_tools?{params}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def write_score(vendor: str, product: str, score: float) -> None:
    payload = {"google_trends_score": score}
    r = requests.patch(
        f'{SUPABASE_URL}/rest/v1/legal_tools?{"Vendor Name"}=eq.{requests.utils.quote(vendor)}'
        f'&{"Product Name"}=eq.{requests.utils.quote(product)}',
        json=payload, headers=HEADERS,
    )
    r.raise_for_status()


# ---------------------------------------------------------------------------
# Trends query
# ---------------------------------------------------------------------------

def get_trends_score(keyword: str, errors_429: list[int]) -> float | None:
    backoff = 60
    for attempt in range(MAX_RETRIES):
        try:
            pt = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
            pt.build_payload([keyword], timeframe="today 12-m", geo="", gprop="")
            df = pt.interest_over_time()
            if df.empty or keyword not in df.columns:
                return 0.0
            return round(float(df[keyword].mean()), 2)

        except Exception as e:
            msg = str(e).lower()
            if "429" in msg or "too many" in msg:
                errors_429[0] += 1
                if errors_429[0] >= MAX_429:
                    raise SystemExit(f"Hit {MAX_429} rate-limit errors — stopping. Re-run later.")
                jitter = random.uniform(0.8, 1.2)
                wait = backoff * jitter
                print(f"    [429] Backing off {wait:.0f}s (error {errors_429[0]}/{MAX_429})")
                time.sleep(wait)
                backoff = min(backoff * 2, 3600)
            else:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(5)
                else:
                    print(f"    [error] {e!s:.80}")
                    return None
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all",   action="store_true", help="Re-score every tool, not just NULLs")
    parser.add_argument("--limit", type=int, default=0, help="Max tools to process this run")
    args = parser.parse_args()

    print("=" * 60)
    print("SUPABASE GOOGLE TRENDS SCORER")
    print("=" * 60)

    tools = fetch_tools(unscored_only=not args.all)
    if args.limit:
        tools = tools[: args.limit]

    total = len(tools)
    print(f"Tools to score: {total}")
    if total == 0:
        print("Nothing to do.")
        return

    est_min = (total * MIN_DELAY) / 60
    print(f"Estimated time: ~{est_min:.0f} min  (rate-limited to ≥{MIN_DELAY}s per request)\n")

    errors_429 = [0]   # mutable counter shared with get_trends_score
    scored = skipped = 0

    for i, tool in enumerate(tools, 1):
        vendor  = tool["Vendor Name"]
        product = tool.get("Product Name") or vendor
        keyword = vendor  # search by vendor name — most recognisable

        print(f"[{i:3}/{total}] {vendor}", end="  ", flush=True)

        score = get_trends_score(keyword, errors_429)
        if score is None:
            print("SKIP (error)")
            skipped += 1
        else:
            try:
                write_score(vendor, product, score)
                print(f"→ {score:.1f}")
                scored += 1
            except Exception as e:
                print(f"SKIP (write error: {e!s:.60})")
                skipped += 1

        # Rate limiting — add jitter to avoid request fingerprinting
        if i < total:
            time.sleep(MIN_DELAY * random.uniform(0.9, 1.2))

    print(f"\n{'='*60}")
    print(f"Done.  Scored: {scored}  Skipped: {skipped}  429 errors: {errors_429[0]}")


if __name__ == "__main__":
    main()
