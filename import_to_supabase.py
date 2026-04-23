"""
import_to_supabase.py
Reads collection_output/REVIEW_BEFORE_IMPORT.csv, skips rows marked SKIP,
and upserts each tool into the Supabase legal_tools table.

Usage:
    python import_to_supabase.py           # live import
    python import_to_supabase.py --dry-run # print what would be imported, no writes
"""

import os, csv, argparse, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",  # upsert behaviour
}

INPUT_CSV = Path("collection_output/REVIEW_BEFORE_IMPORT.csv")

# Columns to strip before sending to Supabase (review metadata only)
REVIEW_COLS = {"REVIEW_SOURCE", "REVIEW_FLAGS", "REVIEW_ACTION"}

# Supabase upsert key — a row is considered a duplicate if both match
UPSERT_ON = ("Vendor Name", "Product Name")


def load_rows() -> list[dict]:
    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def build_payload(row: dict) -> dict:
    """Strip review columns and empty strings; return Supabase-ready dict."""
    payload = {}
    for k, v in row.items():
        if k in REVIEW_COLS:
            continue
        cleaned = v.strip() if isinstance(v, str) else v
        if cleaned not in ("", None):
            payload[k] = cleaned
    return payload


def tool_exists(vendor: str, product: str) -> bool:
    r = requests.get(
        f'{SUPABASE_URL}/rest/v1/legal_tools'
        f'?select="Vendor Name"'
        f'&"Vendor Name"=eq.{requests.utils.quote(vendor)}'
        f'&"Product Name"=eq.{requests.utils.quote(product)}',
        headers=HEADERS,
    )
    r.raise_for_status()
    return len(r.json()) > 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be imported without writing")
    args = parser.parse_args()

    rows = load_rows()
    to_import = [r for r in rows if r.get("REVIEW_ACTION", "").strip().upper() != "SKIP"]
    skipped_review = len(rows) - len(to_import)

    print("=" * 60)
    print("SUPABASE IMPORT" + (" [DRY RUN]" if args.dry_run else ""))
    print("=" * 60)
    print(f"Total rows in CSV:  {len(rows)}")
    print(f"Marked SKIP:        {skipped_review}")
    print(f"To import:          {len(to_import)}")
    print()

    inserted = updated = errors = 0

    for i, row in enumerate(to_import, 1):
        vendor  = row.get("Vendor Name", "").strip()
        product = row.get("Product Name", "").strip()

        if not vendor:
            print(f"  [{i:3}] SKIP — missing Vendor Name")
            errors += 1
            continue

        payload = build_payload(row)

        if args.dry_run:
            exists = tool_exists(vendor, product)
            action = "UPDATE" if exists else "INSERT"
            print(f"  [{i:3}] {action:6}  {vendor} / {product}")
            if exists:
                updated += 1
            else:
                inserted += 1
            continue

        # Live upsert
        try:
            r = requests.post(
                f"{SUPABASE_URL}/rest/v1/legal_tools",
                json=payload,
                headers=HEADERS,
            )
            if r.status_code in (200, 201):
                inserted += 1
                print(f"  [{i:3}] OK      {vendor} / {product}")
            else:
                print(f"  [{i:3}] ERROR   {vendor} / {product}  →  {r.status_code}: {r.text[:120]}")
                errors += 1
        except Exception as e:
            print(f"  [{i:3}] ERROR   {vendor}: {e!s:.80}")
            errors += 1

    print()
    print("=" * 60)
    if args.dry_run:
        print(f"DRY RUN complete.  Would insert: {inserted}  Would update: {updated}")
    else:
        print(f"Import complete.  Inserted: {inserted}  Errors: {errors}")
    print("=" * 60)

    if not args.dry_run and errors == 0:
        print("\nNext steps:")
        print("  python embed_tools.py")
        print("  python supabase_trends_scorer.py")
        print("  python supabase_popularity_scorer.py --new")


if __name__ == "__main__":
    main()
