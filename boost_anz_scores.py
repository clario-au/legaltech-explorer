"""
Manually boost popularity scores for ANZ tools that are penalised by
the global Google Trends scoring formula. These tools have strong ANZ
market presence but low global search volume.

Run once: python boost_anz_scores.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

# ANZ tools being boosted and why
BOOSTS = [
    {"vendor": "Lawcadia",          "score": 65, "reason": "Award-winning ANZ legal ops platform, low global trends but strong ANZ market"},
    {"vendor": "Xakia",             "score": 62, "reason": "Purpose-built ANZ legal ops platform, niche but highly relevant for ANZ queries"},
    {"vendor": "LawVu",             "score": 74, "reason": "Already reasonable — confirming correct score for NZ legal ops"},
    {"vendor": "Persuit",           "score": 58, "reason": "ANZ panel RFP / tendering platform, only tool in its niche"},
]

print("Boosting ANZ tool popularity scores in Supabase...\n")

for b in BOOSTS:
    # Fetch current score first
    res = supabase.table("legal_tools").select('"Vendor Name", "Product Name", popularity_score') \
        .eq("Vendor Name", b["vendor"]).execute()

    if not res.data:
        print(f"  NOT FOUND: {b['vendor']}")
        continue

    for tool in res.data:
        old = tool.get("popularity_score", "?")
        supabase.table("legal_tools") \
            .update({"popularity_score": b["score"]}) \
            .eq("Vendor Name", b["vendor"]) \
            .eq("Product Name", tool["Product Name"]) \
            .execute()
        print(f"  OK {b['vendor']} | {tool['Product Name']}")
        print(f"    {old} -> {b['score']}  ({b['reason']})")

print("\nDone. Also update CSV to keep local data in sync...")

# Update local CSV too
import csv, shutil
csv_path = "merged_pref_top50_updated.csv"
shutil.copy(csv_path, csv_path + ".backup_before_anz_boost")

rows = []
with open(csv_path, encoding="utf-8", errors="replace") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for row in reader:
        for b in BOOSTS:
            if row.get("Vendor Name","").strip().lower() == b["vendor"].lower():
                row["popularity_score"] = str(b["score"])
        rows.append(row)

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"CSV updated. Backup at {csv_path}.backup_before_anz_boost")
