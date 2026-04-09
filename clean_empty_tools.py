"""
Remove tools from the database that have no associated data or no description.
Filters out tools with missing critical information.
"""

import pandas as pd

def is_empty_or_nan(value):
    """Check if a value is empty, NaN, or just whitespace."""
    if pd.isna(value):
        return True
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or stripped.lower() in ['nan', 'n/a', 'none', '']:
            return True
    return False

def has_sufficient_data(row):
    """
    Determine if a tool has sufficient data to be useful.

    Must have at least:
    - Vendor Name
    - Either Product Description OR Vendor Overview
    """
    # Must have vendor name
    if is_empty_or_nan(row.get('Vendor Name')):
        return False

    # Must have at least some description
    has_product_desc = not is_empty_or_nan(row.get('Product Description'))
    has_vendor_overview = not is_empty_or_nan(row.get('Vendor Overview'))

    if not (has_product_desc or has_vendor_overview):
        return False

    return True

def main():
    """Main execution."""

    print("="*80)
    print("CLEANING DATABASE - REMOVING EMPTY TOOLS")
    print("="*80)

    # Load database
    database_file = 'merged_pref_top50_updated.csv'

    try:
        df = pd.read_csv(database_file)
        print(f"\nLoaded: {database_file}")
        print(f"Total tools before cleaning: {len(df)}")
    except FileNotFoundError:
        print(f"\nERROR: {database_file} not found!")
        return

    # Count tools that will be removed
    print("\nAnalyzing tools...")

    # Track removal reasons
    no_vendor_name = 0
    no_description = 0

    tools_to_keep = []
    tools_removed = []

    for idx, row in df.iterrows():
        vendor_name = row.get('Vendor Name', '')

        # Check vendor name
        if is_empty_or_nan(vendor_name):
            no_vendor_name += 1
            tools_removed.append({
                'reason': 'No vendor name',
                'vendor': str(vendor_name),
                'product': str(row.get('Product Name', ''))
            })
            continue

        # Check descriptions
        has_product_desc = not is_empty_or_nan(row.get('Product Description'))
        has_vendor_overview = not is_empty_or_nan(row.get('Vendor Overview'))

        if not (has_product_desc or has_vendor_overview):
            no_description += 1
            tools_removed.append({
                'reason': 'No description',
                'vendor': str(vendor_name),
                'product': str(row.get('Product Name', ''))
            })
            continue

        # Keep this tool
        tools_to_keep.append(row)

    # Create cleaned dataframe
    df_cleaned = pd.DataFrame(tools_to_keep)

    print(f"\n{'='*80}")
    print("REMOVAL SUMMARY")
    print(f"{'='*80}")
    print(f"Tools with no vendor name: {no_vendor_name}")
    print(f"Tools with no description: {no_description}")
    print(f"Total tools removed: {len(tools_removed)}")
    print(f"Total tools kept: {len(df_cleaned)}")

    # Show some examples of removed tools
    if tools_removed:
        print(f"\n{'='*80}")
        print("EXAMPLES OF REMOVED TOOLS (First 10)")
        print(f"{'='*80}")
        print(f"{'Reason':<20} {'Vendor Name':<30} {'Product Name':<30}")
        print("-"*80)
        for item in tools_removed[:10]:
            reason = item['reason'][:18]
            vendor = item['vendor'][:28]
            product = item['product'][:28]
            print(f"{reason:<20} {vendor:<30} {product:<30}")

        if len(tools_removed) > 10:
            print(f"... and {len(tools_removed) - 10} more")

    # Save cleaned database
    if len(df_cleaned) < len(df):
        # Backup original
        backup_file = database_file.replace('.csv', '_backup_before_cleaning.csv')
        df.to_csv(backup_file, index=False)
        print(f"\n{'='*80}")
        print("SAVING")
        print(f"{'='*80}")
        print(f"Backup saved: {backup_file}")

        # Save cleaned version
        df_cleaned.to_csv(database_file, index=False)
        print(f"Cleaned database saved: {database_file}")
        print(f"\nRemoved {len(df) - len(df_cleaned)} tools ({(len(df) - len(df_cleaned))/len(df)*100:.1f}%)")
        print(f"Remaining: {len(df_cleaned)} tools")

        print(f"\n{'='*80}")
        print("NEXT STEP")
        print(f"{'='*80}")
        print("Run update_html_data.py to update the web UI with cleaned data")
    else:
        print(f"\n{'='*80}")
        print("NO CHANGES NEEDED")
        print(f"{'='*80}")
        print("All tools have sufficient data. No cleaning required.")

if __name__ == "__main__":
    main()
