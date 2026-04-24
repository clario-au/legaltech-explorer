"""
fetch_missing_logos.py
Fetches logos for vendors that don't yet have one in the logos/ folder.
Uses Clearbit logo API (logo.clearbit.com/{domain}) — no API key needed.
Does NOT touch Supabase. Saves files to logos/{slug}.png for review.

Usage:
    python fetch_missing_logos.py           # all missing (398)
    python fetch_missing_logos.py --limit 50
"""

import os, re, time, argparse, requests
from dotenv import load_dotenv

load_dotenv()

LOGOS_DIR = "logos_review"
GOOGLE_FAVICON_URL = "https://www.google.com/s2/favicons?domain={domain}&sz=128"
DDG_FAVICON_URL = "https://icons.duckduckgo.com/ip3/{domain}.ico"
GENERIC_THRESHOLD = 800  # bytes — Google's generic globe is 726b; skip anything at or below
DELAY = 0.5  # seconds between requests

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SB_HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}


def vendor_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def existing_slugs() -> set:
    slugs = set()
    for folder in ("logos", "logos_review"):
        if os.path.isdir(folder):
            slugs |= {
                os.path.splitext(f)[0].lower()
                for f in os.listdir(folder)
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
            }
    return slugs


def fetch_all_vendors() -> list[tuple[str, str, str]]:
    """Returns list of (vendor_name, slug, domain) for vendors missing a logo."""
    all_tools, offset = [], 0
    while True:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/legal_tools"
            f"?select=Vendor+Name,Vendor+Website&limit=1000&offset={offset}",
            headers=SB_HEADERS,
        )
        r.raise_for_status()
        batch = r.json()
        all_tools.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000

    existing = existing_slugs()
    seen, missing = set(), []
    for t in all_tools:
        v = (t.get("Vendor Name") or "").strip()
        if not v:
            continue
        s = vendor_slug(v)
        if s in seen or s in existing:
            continue
        seen.add(s)
        raw_domain = (t.get("Vendor Website") or "").strip()
        domain = raw_domain.replace("https://", "").replace("http://", "").split("/")[0]
        if domain and "." in domain:
            missing.append((v, s, domain))
        else:
            missing.append((v, s, ""))  # no domain — will attempt name-based guess

    return missing


def domain_from_slug(slug: str) -> str:
    """Fallback: guess domain as slug.com"""
    return f"{slug}.com"


def fetch_logo(domain: str, slug: str) -> bool:
    """Try Google favicon then DuckDuckGo. Skip generic placeholders."""
    for url_tpl in (GOOGLE_FAVICON_URL, DDG_FAVICON_URL):
        url = url_tpl.format(domain=domain)
        try:
            r = requests.get(url, timeout=8)
            ct = r.headers.get("content-type", "")
            if r.status_code == 200 and "image" in ct and len(r.content) > GENERIC_THRESHOLD:
                path = os.path.join(LOGOS_DIR, f"{slug}.png")
                with open(path, "wb") as f:
                    f.write(r.content)
                return True
        except Exception:
            continue
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Max logos to fetch (0=all)")
    args = parser.parse_args()

    print("Fetching vendor list from Supabase...")
    vendors = fetch_all_vendors()
    print(f"Vendors missing logos: {len(vendors)}")

    if args.limit:
        vendors = vendors[: args.limit]
        print(f"Limiting to first {args.limit}")

    print()
    ok = failed = skipped = 0

    for i, (name, slug, domain) in enumerate(vendors, 1):
        if not domain:
            domain = domain_from_slug(slug)
            src = "guessed"
        else:
            src = "db"

        success = fetch_logo(domain, slug)
        if success:
            ok += 1
            print(f"  [{i:3}] OK    {slug:38s}  ({domain})")
        else:
            failed += 1
            print(f"  [{i:3}] MISS  {slug:38s}  ({domain})")

        time.sleep(DELAY)

    print()
    print(f"Done.  Saved: {ok}  Not found: {failed}")
    print(f"Check logos/ folder — filenames follow the site convention (slug.png).")
    print("Nothing written to Supabase. Review and delete any wrong ones before deploying.")


if __name__ == "__main__":
    main()
