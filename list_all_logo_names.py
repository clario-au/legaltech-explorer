"""
Generate a simple alphabetical list of ALL vendor logo filenames.
Perfect for working through manually.
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

    if not csv_file.exists():
        print(f"Error: {csv_file} not found")
        return

    # Read CSV
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        vendors = []
        for row in reader:
            vendor_name = row.get('Vendor Name', '').strip()
            if vendor_name:
                vendors.append(vendor_name)

    # Get unique vendors and sort
    unique_vendors = sorted(set(vendors))

    # Print header
    print("=" * 80)
    print(f"ALL LOGO FILENAMES - ALPHABETICAL LIST")
    print(f"Total vendors: {len(unique_vendors)}")
    print("=" * 80)
    print()

    # Print simple list
    for vendor in unique_vendors:
        slug = vendor_slug(vendor)
        print(f"{vendor:<50} → {slug}.png")

    # Save to file
    output_file = Path('ALL_LOGO_NAMES.txt')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("ALL LOGO FILENAMES - ALPHABETICAL LIST\n")
        f.write("=" * 80 + "\n")
        f.write(f"Total vendors: {len(unique_vendors)}\n")
        f.write("=" * 80 + "\n\n")

        for vendor in unique_vendors:
            slug = vendor_slug(vendor)
            f.write(f"{vendor:<50} → {slug}.png\n")

    print()
    print("=" * 80)
    print(f"✓ Saved to {output_file}")
    print("=" * 80)

if __name__ == '__main__':
    main()
