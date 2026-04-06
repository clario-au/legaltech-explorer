"""
Investigate why the merge creates extra rows.
"""
import pandas as pd
from pathlib import Path
import sys

# Fix UTF-8 encoding on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    print("="*80)
    print("INVESTIGATING MERGE ROW COUNT ISSUE")
    print("="*80)

    # Load main database
    db_file = Path('merged_pref_top50_updated.csv')
    print(f"\nLoading main database: {db_file}")
    df_main = pd.read_csv(db_file)
    print(f"  - Rows: {len(df_main)}")

    # Load Google Trends data
    trends_files = list(Path('.').glob('google_trends_results_*.csv'))
    latest_trends = sorted(trends_files)[-1]
    print(f"\nLoading Google Trends data: {latest_trends}")
    df_trends = pd.read_csv(latest_trends)
    print(f"  - Rows: {len(df_trends)}")

    # Check for duplicate vendor names in main database
    print("\n" + "="*80)
    print("CHECKING FOR DUPLICATES IN MAIN DATABASE")
    print("="*80)
    main_duplicates = df_main[df_main.duplicated(subset=['Vendor Name'], keep=False)]
    if len(main_duplicates) > 0:
        print(f"\n⚠ Found {len(main_duplicates)} duplicate vendor names in main database:")
        for name in main_duplicates['Vendor Name'].unique():
            count = len(df_main[df_main['Vendor Name'] == name])
            print(f"  - '{name}' appears {count} times")
    else:
        print("\n✓ No duplicates found in main database")

    # Check for duplicate vendor names in trends data
    print("\n" + "="*80)
    print("CHECKING FOR DUPLICATES IN TRENDS DATA")
    print("="*80)
    trends_duplicates = df_trends[df_trends.duplicated(subset=['Vendor Name'], keep=False)]
    if len(trends_duplicates) > 0:
        print(f"\n⚠ Found {len(trends_duplicates)} duplicate vendor names in trends data:")
        for name in trends_duplicates['Vendor Name'].unique():
            count = len(df_trends[df_trends['Vendor Name'] == name])
            print(f"  - '{name}' appears {count} times")
            # Show details
            dupes = df_trends[df_trends['Vendor Name'] == name]
            for idx, row in dupes.iterrows():
                print(f"    → avg_interest: {row['avg_interest']}, status: {row['status']}")
    else:
        print("\n✓ No duplicates found in trends data")

    # Perform the merge to see what happens
    print("\n" + "="*80)
    print("PERFORMING TEST MERGE")
    print("="*80)
    df_trends_merge = df_trends[['Vendor Name', 'avg_interest']].copy()
    df_trends_merge = df_trends_merge.rename(columns={'avg_interest': 'google_trends_score'})

    df_merged = df_main.merge(df_trends_merge, on='Vendor Name', how='left')

    print(f"\nMerge results:")
    print(f"  - Main rows: {len(df_main)}")
    print(f"  - Merged rows: {len(df_merged)}")
    print(f"  - Difference: {len(df_merged) - len(df_main)}")

    # If there are extra rows, identify them
    if len(df_merged) > len(df_main):
        print("\n⚠ Extra rows created during merge")
        print("\nChecking which vendor names created duplicates...")

        # Count occurrences in merged data
        merged_counts = df_merged['Vendor Name'].value_counts()
        duplicated_names = merged_counts[merged_counts > 1]

        if len(duplicated_names) > 0:
            print(f"\nVendor names that appear multiple times after merge:")
            for name, count in duplicated_names.items():
                print(f"  - '{name}' appears {count} times")

                # Show the rows
                print(f"\n    In main database:")
                main_rows = df_main[df_main['Vendor Name'] == name]
                print(f"      Count: {len(main_rows)}")

                print(f"\n    In trends data:")
                trends_rows = df_trends[df_trends['Vendor Name'] == name]
                print(f"      Count: {len(trends_rows)}")
                if len(trends_rows) > 0:
                    for idx, row in trends_rows.iterrows():
                        print(f"        → avg_interest: {row['avg_interest']}")

    print("\n" + "="*80)
    print("INVESTIGATION COMPLETE")
    print("="*80)

if __name__ == "__main__":
    main()
