"""
Shows the required logo filenames for each vendor in the CSV.
Helps you identify which logos are missing and what to name them.
"""
import csv
import re
import sys
from pathlib import Path

# Fix UTF-8 encoding on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def vendor_slug(name):
    """Convert vendor name to slug format (lowercase, alphanumeric only)"""
    return re.sub(r'[^a-z0-9]', '', str(name).lower())

def main():
    csv_file = Path('merged_pref_top50_updated.csv')
    logos_dir = Path('logos')

    if not csv_file.exists():
        print(f"Error: {csv_file} not found")
        return

    if not logos_dir.exists():
        print(f"Error: {logos_dir}/ directory not found")
        return

    # Read CSV
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        vendors = []
        for row in reader:
            vendor_name = row.get('Vendor Name', '').strip()
            if vendor_name:
                vendors.append(vendor_name)

    # Get unique vendors
    unique_vendors = sorted(set(vendors))

    # Check which logos exist
    existing_logos = set()
    for ext in ['.png', '.jpg', '.jpeg', '.webp']:
        existing_logos.update([f.stem for f in logos_dir.glob(f'*{ext}')])

    print("=" * 80)
    print("LOGO FILENAME REFERENCE")
    print("=" * 80)
    print(f"\nTotal unique vendors: {len(unique_vendors)}")
    print(f"Existing logos: {len(existing_logos)}")
    print(f"Missing logos: {len(unique_vendors) - len(existing_logos)}\n")

    # Show all vendors with their required filename
    print("\n" + "=" * 80)
    print("ALL VENDORS - Required Logo Filenames")
    print("=" * 80)
    print(f"{'Vendor Name':<50} {'Logo Filename':<30} {'Status'}")
    print("-" * 80)

    for vendor in unique_vendors:
        slug = vendor_slug(vendor)
        status = "✓ EXISTS" if slug in existing_logos else "✗ MISSING"
        print(f"{vendor:<50} {slug}.png{' ':<21} {status}")

    # Show only missing logos
    missing_vendors = [v for v in unique_vendors if vendor_slug(v) not in existing_logos]

    if missing_vendors:
        print("\n" + "=" * 80)
        print("MISSING LOGOS ONLY")
        print("=" * 80)
        print(f"{'Vendor Name':<50} {'Required Filename'}")
        print("-" * 80)

        for vendor in missing_vendors:
            slug = vendor_slug(vendor)
            print(f"{vendor:<50} {slug}.png")

        # Create a quick reference file
        ref_file = Path('MISSING_LOGOS.txt')
        with open(ref_file, 'w', encoding='utf-8') as f:
            f.write("MISSING LOGOS - Quick Reference\n")
            f.write("=" * 80 + "\n\n")
            f.write("Copy this list when searching for logos:\n\n")
            for vendor in missing_vendors:
                slug = vendor_slug(vendor)
                f.write(f"{vendor:<50} → {slug}.png\n")

        print(f"\n✓ Created {ref_file} with list of missing logos")
    else:
        print("\n✓ All logos present!")

    # Show filename conversion examples
    print("\n" + "=" * 80)
    print("NAMING CONVENTION EXAMPLES")
    print("=" * 80)
    examples = [
        ("Ace4 AI", "ace4ai.png"),
        ("Ironclad, Inc.", "ironcladinc.png"),
        ("CircleUp Technologies Pty Ltd", "circleuptechnologiesptyltd.png"),
        ("DeepJudge AG", "deepjudgeag.png"),
        ("Kelsen Legal Technologies Inc.", "kelsenlegaltechnologiesinc.png"),
    ]

    print(f"\n{'Original Name':<40} → {'Logo Filename'}")
    print("-" * 80)
    for orig, filename in examples:
        print(f"{orig:<40} → {filename}")

    print("\n" + "=" * 80)
    print("QUICK TIPS")
    print("=" * 80)
    print("""
1. Filename = vendor name in lowercase, alphanumeric only
2. Remove ALL spaces, dots, commas, hyphens, etc.
3. Keep numbers (e.g., "Ace4 AI" → "ace4ai")
4. Preferred format: .png with transparent background
5. Size: 256x256 pixels (will auto-scale)
6. Place in the logos/ folder

Example workflow:
1. Find missing vendor in list above
2. Search Google: "[Vendor Name] logo png"
3. Download logo
4. Rename to the slug format shown above
5. Save to logos/ folder
    """)

if __name__ == '__main__':
    main()
