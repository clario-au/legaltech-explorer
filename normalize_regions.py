"""
normalize_regions.py
Standardises the "Regions Served" field across all tools in Supabase.

Canonical regions (7 values):
    Global
    North America (US & Canada)
    Europe (UK & EU)
    Asia-Pacific (APAC)
    Australia & New Zealand (ANZ)
    Middle East & Africa
    Latin America

Rules:
  - "Global" / "Worldwide" / "Globally" etc → ["Global"]
    (Global subsumes everything; no need to also list sub-regions)
  - "Global (including Australia/ANZ)" → ["Global"]
    (the ANZ callout is informational, not structural)
  - Individual countries / alternate spellings → mapped to their parent region
  - Junk values (non-geographic industry names) → left blank / cleared
  - A tool may end up with multiple canonical values (e.g. "Australia & New Zealand (ANZ); Asia-Pacific (APAC)")

Usage:
    python normalize_regions.py --dry-run    # preview changes without writing
    python normalize_regions.py              # write to Supabase
"""

import os, re, requests, argparse
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# ---------------------------------------------------------------------------
# Canonical region definitions
# ---------------------------------------------------------------------------

CANONICAL = [
    "Global",
    "North America (US & Canada)",
    "Europe (UK & EU)",
    "Asia-Pacific (APAC)",
    "Australia & New Zealand (ANZ)",
    "Middle East & Africa",
    "Latin America",
]

# Each rule is (list-of-patterns, canonical-value).
# Patterns are matched case-insensitively against each split token.
# Order matters — Global checked first so "21 Countries; Global" → Global.
RULES = [
    # ---------- Global ----------
    (["global", "worldwide", "globally", r"\d+ countries", r"70\+"], "Global"),

    # ---------- Latin America ----------
    (["latin america", "peru", "ecuador", "chile", "colombia", "panama",
      "guatemala", "mexico", "dominican", "americas"], "Latin America"),

    # ---------- North America ----------
    (["north america", r"\busa\b", r"\bu\.s\.", r"\bus\b", "united states",
      "nationwide.*united states", "canada"], "North America (US & Canada)"),

    # ---------- Europe ----------
    (["europe", r"\beu\b", "european union", "uk and ireland", "england and wales",
      r"\buk\b", "united kingdom", "germany", "netherlands", "switzerland",
      "austria", "poland", "belgium", "italy", "czech", "romania", "hungary",
      "slovakia", "denmark", "sweden"], "Europe (UK & EU)"),

    # ---------- ANZ (before APAC so AU isn't swallowed by it) ----------
    (["australia", "new zealand", r"\banz\b"], "Australia & New Zealand (ANZ)"),

    # ---------- Asia-Pacific (APAC) ----------
    (["asia.pacific", r"\bapac\b", "asia", "hong kong", "singapore",
      "vietnam"], "Asia-Pacific (APAC)"),

    # ---------- Middle East & Africa ----------
    (["middle east", "africa"], "Middle East & Africa"),
]

# Tokens that indicate junk data — clear the whole field
JUNK_SIGNALS = ["financial services", "insurance", "healthcare", "tech",
                "regulated industries", "regions served"]


def token_to_canonical(token: str) -> str | None:
    t = token.strip().lower()
    if not t:
        return None
    for junk in JUNK_SIGNALS:
        if junk in t:
            return None  # signals whole row is junk
    for patterns, canon in RULES:
        for pat in patterns:
            if re.search(pat, t, re.IGNORECASE):
                return canon
    return None


def normalize(raw: str) -> str:
    """Return semicolon-separated canonical string, or '' if junk/empty."""
    if not raw or str(raw).strip() in ("", "nan"):
        return ""

    # Check for junk row first
    for junk in JUNK_SIGNALS:
        if junk.lower() in raw.lower():
            return ""

    tokens = [t.strip() for t in re.split(r"[;,]", raw) if t.strip()]
    seen = set()
    result = []

    for token in tokens:
        canon = token_to_canonical(token)
        if canon and canon not in seen:
            seen.add(canon)
            result.append(canon)

    # If Global is present it subsumes everything else
    if "Global" in seen:
        return "Global"

    return "; ".join(result)


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def fetch_tools() -> list[dict]:
    r = requests.get(
        f'{SUPABASE_URL}/rest/v1/legal_tools'
        f'?select="Vendor Name","Product Name","Regions Served"&limit=1000',
        headers=HEADERS,
    )
    r.raise_for_status()
    return r.json()


def write_region(vendor: str, product: str, value: str | None) -> None:
    payload = {"Regions Served": value if value else None}
    r = requests.patch(
        f'{SUPABASE_URL}/rest/v1/legal_tools'
        f'?"Vendor Name"=eq.{requests.utils.quote(vendor)}'
        f'&"Product Name"=eq.{requests.utils.quote(product)}',
        json=payload,
        headers=HEADERS,
    )
    r.raise_for_status()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print changes without writing to Supabase")
    args = parser.parse_args()

    tools = fetch_tools()
    print(f"Tools fetched: {len(tools)}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE WRITE'}\n")

    changed = 0
    cleared = 0
    unchanged = 0

    for t in tools:
        vendor  = t["Vendor Name"]
        product = t.get("Product Name") or vendor
        raw     = t.get("Regions Served") or ""
        norm    = normalize(raw)

        if str(raw).strip() == str(norm).strip():
            unchanged += 1
            continue

        label = "CLEAR" if (raw and not norm) else "CHANGE"
        print(f"  [{label}] {vendor!r}")
        print(f"    before: {raw!r}")
        print(f"    after:  {norm!r}")

        if not args.dry_run:
            try:
                write_region(vendor, product, norm or None)
                changed += 1
            except Exception as e:
                print(f"    ERROR: {e!s:.80}")
        else:
            changed += 1

        if not norm:
            cleared += 1

    print(f"\n{'='*60}")
    print(f"Changed: {changed}  Cleared (junk): {cleared}  Unchanged: {unchanged}")
    if args.dry_run:
        print("(Dry run — nothing written)")


if __name__ == "__main__":
    main()
