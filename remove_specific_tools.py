"""
Remove specific tools from the database by vendor name.
"""

import pandas as pd

def main():
    """Main execution."""

    print("="*80)
    print("REMOVING SPECIFIC TOOLS")
    print("="*80)

    # Tools to remove
    tools_to_remove = ['Covenant', 'Maeven', 'PaxAI']

    # Load database
    database_file = 'merged_pref_top50_updated.csv'

    try:
        df = pd.read_csv(database_file)
        print(f"\nLoaded: {database_file}")
        print(f"Total tools before removal: {len(df)}")
    except FileNotFoundError:
        print(f"\nERROR: {database_file} not found!")
        return

    # Find tools to remove
    print(f"\nLooking for tools to remove: {', '.join(tools_to_remove)}")

    # Create mask for tools to keep (case-insensitive matching)
    mask_to_remove = df['Vendor Name'].str.lower().isin([t.lower() for t in tools_to_remove])

    # Show what will be removed
    if mask_to_remove.any():
        print(f"\nFound {mask_to_remove.sum()} tools to remove:")
        print(df[mask_to_remove][['Vendor Name', 'Product Name']].to_string(index=False))

        # Remove the tools
        df_cleaned = df[~mask_to_remove].copy()

        # Backup original
        backup_file = database_file.replace('.csv', '_backup_before_removal.csv')
        df.to_csv(backup_file, index=False)

        # Save cleaned version
        df_cleaned.to_csv(database_file, index=False)

        print(f"\n{'='*80}")
        print("COMPLETE")
        print(f"{'='*80}")
        print(f"Backup saved: {backup_file}")
        print(f"Updated database: {database_file}")
        print(f"Removed: {mask_to_remove.sum()} tools")
        print(f"Remaining: {len(df_cleaned)} tools")

        print(f"\n{'='*80}")
        print("NEXT STEP")
        print(f"{'='*80}")
        print("Run update_html_data.py to update the web UI")

    else:
        print("\nNo matching tools found. Nothing to remove.")

if __name__ == "__main__":
    main()
