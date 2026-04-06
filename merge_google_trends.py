"""
Merge Google Trends data into the main database.
Safely adds the avg_interest column without disrupting existing functionality.
"""

import pandas as pd
from pathlib import Path
import sys

# Fix UTF-8 encoding on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    print("="*80)
    print("MERGING GOOGLE TRENDS DATA INTO MAIN DATABASE")
    print("="*80)

    # Load main database
    db_file = Path('merged_pref_top50_updated.csv')
    if not db_file.exists():
        print(f"Error: {db_file} not found")
        return

    print(f"\nLoading main database: {db_file}")
    df_main = pd.read_csv(db_file)
    print(f"  - Loaded {len(df_main)} tools")
    print(f"  - Existing columns: {len(df_main.columns)}")

    # Find latest Google Trends file
    trends_files = list(Path('.').glob('google_trends_results_*.csv'))
    if not trends_files:
        print("\nError: No Google Trends results files found")
        return

    latest_trends = sorted(trends_files)[-1]
    print(f"\nLoading Google Trends data: {latest_trends}")
    df_trends = pd.read_csv(latest_trends)
    print(f"  - Loaded {len(df_trends)} tools")

    # Create backup
    backup_file = db_file.with_suffix('.csv.backup')
    print(f"\nCreating backup: {backup_file}")
    df_main.to_csv(backup_file, index=False)

    # Merge Google Trends data
    # Use avg_interest as the Google Trends score (0-100)
    print(f"\nMerging Google Trends data...")

    # Prepare trends data for merge - only keep successful results
    df_trends_merge = df_trends[['Vendor Name', 'avg_interest']].copy()
    df_trends_merge = df_trends_merge.rename(columns={'avg_interest': 'google_trends_score'})

    # Deduplicate trends data - keep the first occurrence for each vendor
    # (This prevents Cartesian product when both datasets have duplicates)
    print(f"  - Trends data before deduplication: {len(df_trends_merge)} rows")
    df_trends_merge = df_trends_merge.drop_duplicates(subset=['Vendor Name'], keep='first')
    print(f"  - Trends data after deduplication: {len(df_trends_merge)} rows")

    # Remove any existing google_trends_score column
    if 'google_trends_score' in df_main.columns:
        print("  - Removing existing google_trends_score column")
        df_main = df_main.drop(columns=['google_trends_score'])

    # Merge on Vendor Name (left join to keep all main database entries)
    df_merged = df_main.merge(df_trends_merge, on='Vendor Name', how='left')

    # Fill NaN values with 0 (tools without Google Trends data)
    df_merged['google_trends_score'] = df_merged['google_trends_score'].fillna(0)

    print(f"  - Merged successfully")
    print(f"  - Tools with Google Trends data: {(df_merged['google_trends_score'] > 0).sum()}")
    print(f"  - Tools without Google Trends data (set to 0): {(df_merged['google_trends_score'] == 0).sum()}")

    # Verify data integrity
    print(f"\nVerifying data integrity...")
    print(f"  - Original row count: {len(df_main)}")
    print(f"  - Merged row count: {len(df_merged)}")
    print(f"  - Original column count: {len(df_main.columns)}")
    print(f"  - Merged column count: {len(df_merged.columns)}")

    if len(df_main) != len(df_merged):
        print("\n❌ ERROR: Row count changed during merge!")
        return

    # Save merged database
    print(f"\nSaving merged database to: {db_file}")
    df_merged.to_csv(db_file, index=False)

    print("\n" + "="*80)
    print("✓ MERGE COMPLETE")
    print("="*80)
    print(f"\nSummary:")
    print(f"  - Main database updated: {db_file}")
    print(f"  - Backup created: {backup_file}")
    print(f"  - New column added: google_trends_score")
    print(f"  - Total tools: {len(df_merged)}")
    print(f"  - Tools with trends data: {(df_merged['google_trends_score'] > 0).sum()}")

    # Show sample of merged data
    print(f"\nSample of merged data:")
    sample = df_merged[['Vendor Name', 'google_trends_score', 'popularity_score']].head(5)
    for idx, row in sample.iterrows():
        print(f"  {row['Vendor Name']:30s}: trends={row['google_trends_score']:5.1f}, popularity={row['popularity_score']:5.1f}")

if __name__ == "__main__":
    main()
