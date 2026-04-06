import pandas as pd
import re

def normalize_name(name):
    """Normalize a vendor/product name for comparison."""
    if pd.isna(name):
        return ""

    name = str(name).lower().strip()

    # Remove common legal suffixes
    suffixes = [
        r'\s+inc\.?$', r'\s+llc\.?$', r'\s+ltd\.?$', r'\s+limited$',
        r'\s+corporation$', r'\s+corp\.?$', r'\s+gmbh$', r'\s+ag$',
        r'\s+sa$', r'\s+bv$', r'\s+pty$', r'\s+co\.?$', r'\s+llp$',
        r'\s+s\.?l\.?$'  # Add S.L. for Spanish companies
    ]
    for suffix in suffixes:
        name = re.sub(suffix, '', name, flags=re.IGNORECASE)

    # Remove "by [company]" patterns
    name = re.sub(r'\s+by\s+.*$', '', name)

    # Remove special characters and extra spaces
    name = re.sub(r'[^\w\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()

    return name

def is_similar(name1, name2):
    """
    Check if two names are similar enough to be considered the same tool.
    Uses CONSERVATIVE matching to minimize false positives.
    """
    norm1 = normalize_name(name1)
    norm2 = normalize_name(name2)

    if not norm1 or not norm2:
        return False

    # Exact match after normalization
    if norm1 == norm2:
        return True

    # Split into words
    words1 = norm1.split()
    words2 = norm2.split()

    # For single-word names: check if that word appears in the other name
    # Example: "Bigle" matches "Bigle CLM" or "Bigle Iberia"
    if len(words1) == 1:
        # Single word from name1 must appear in name2
        # AND must be a significant word (>2 chars to avoid matching "AI", "by", etc.)
        if len(words1[0]) > 2 and words1[0] in words2:
            return True

    if len(words2) == 1:
        # Single word from name2 must appear in name1
        if len(words2[0]) > 2 and words2[0] in words1:
            return True

    # For multi-word names: use set matching
    set1 = set(words1)
    set2 = set(words2)

    # Skip if either set is empty
    if not set1 or not set2:
        return False

    # Calculate overlap
    overlap = set1 & set2

    # Determine shorter and longer
    if len(set1) <= len(set2):
        shorter = set1
        longer = set2
    else:
        shorter = set2
        longer = set1

    # For 2-word names: both words must match
    if len(shorter) == 2:
        return shorter == overlap

    # For 3+ word names: at least 2 words must match AND 75% overlap
    if len(shorter) >= 3:
        overlap_pct = len(overlap) / len(shorter)
        return len(overlap) >= 2 and overlap_pct >= 0.75

    return False

# Read files
print("Reading legal_tools_all.xlsx...")
xlsx_df = pd.read_excel('legal_tools_all.xlsx')

print("Reading merged_pref_top50.csv...")
csv_df = pd.read_csv('merged_pref_top50.csv')

print(f"\nXLSX has {len(xlsx_df)} rows")
print(f"CSV has {len(csv_df)} rows")

# Get names
xlsx_vendors = xlsx_df['vendor_name'].dropna().unique()
csv_vendors = csv_df['Vendor Name'].dropna().unique()
csv_products = csv_df['Product Name'].dropna().unique()
all_csv_names = set(list(csv_vendors) + list(csv_products))

print(f"\nTotal unique names in legal_tools_all.xlsx: {len(xlsx_vendors)}")
print(f"Total unique names in merged_pref_top50.csv: {len(all_csv_names)}")
print(f"  - Vendors: {len(csv_vendors)}")
print(f"  - Products: {len(csv_products)}")

# Find matches
missing_vendors = []
found_matches = []

for xlsx_vendor in xlsx_vendors:
    is_in_db = False
    matched_with = None

    for csv_name in all_csv_names:
        if is_similar(xlsx_vendor, csv_name):
            is_in_db = True
            matched_with = csv_name
            break

    if is_in_db:
        found_matches.append((xlsx_vendor, matched_with))
    else:
        missing_vendors.append(xlsx_vendor)

print(f"\nVendors/Tools found in database: {len(found_matches)}")
print(f"Vendors/Tools NOT in current database: {len(missing_vendors)}")

# Save results
missing_sorted = sorted(missing_vendors)

with open('tools_not_in_database.txt', 'w', encoding='utf-8') as f:
    f.write(f"Vendors/Tools in legal_tools_all.xlsx NOT in merged_pref_top50.csv\n")
    f.write(f"(Using conservative fuzzy matching to avoid duplicates)\n")
    f.write(f"Total: {len(missing_sorted)}\n")
    f.write("="*80 + "\n\n")
    for i, tool in enumerate(missing_sorted, 1):
        f.write(f"{i}. {tool}\n")

with open('tools_found_in_database.txt', 'w', encoding='utf-8') as f:
    f.write(f"Vendors/Tools in legal_tools_all.xlsx FOUND in merged_pref_top50.csv\n")
    f.write(f"(Please review for false positives)\n")
    f.write(f"Total: {len(found_matches)}\n")
    f.write("="*80 + "\n\n")
    for i, (xlsx_name, csv_name) in enumerate(sorted(found_matches), 1):
        if normalize_name(xlsx_name) != normalize_name(csv_name):
            f.write(f"{i}. {xlsx_name} ~= {csv_name}\n")
        else:
            f.write(f"{i}. {xlsx_name}\n")

print(f"\nResults saved to:")
print(f"  - tools_not_in_database.txt ({len(missing_sorted)} tools)")
print(f"  - tools_found_in_database.txt ({len(found_matches)} tools)")

# Print first 50 missing tools
print(f"\nFirst 50 missing tools:")
print("="*80)
for i, tool in enumerate(missing_sorted[:50], 1):
    print(f"{i:3d}. {tool}")

if len(missing_sorted) > 50:
    print(f"\n  ... and {len(missing_sorted) - 50} more (see tools_not_in_database.txt)")

# Print fuzzy matches
print(f"\n\nFuzzy matches (name variations):")
print("="*80)
fuzzy_matches = [(x, c) for (x, c) in sorted(found_matches)
                 if normalize_name(x) != normalize_name(c)]
for i, (xlsx_name, csv_name) in enumerate(fuzzy_matches[:30], 1):
    print(f"{i:3d}. '{xlsx_name}' ~= '{csv_name}'")

if len(fuzzy_matches) > 30:
    print(f"\n  ... and {len(fuzzy_matches) - 30} more fuzzy matches")

print(f"\n\nSummary:")
print(f"  Exact matches: {len(found_matches) - len(fuzzy_matches)}")
print(f"  Fuzzy matches: {len(fuzzy_matches)}")
print(f"  Not in database: {len(missing_vendors)}")
print(f"\nReview 'tools_found_in_database.txt' for any false positives!")
