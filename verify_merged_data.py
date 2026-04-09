"""
Verify the Google Trends data was merged correctly
"""
import pandas as pd
import sys

# Fix UTF-8 encoding on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

df = pd.read_csv('merged_pref_top50_updated.csv')

print("="*80)
print("VERIFYING MERGED GOOGLE TRENDS DATA")
print("="*80)

# Check if column exists
if 'google_trends_score' in df.columns:
    print("\n✓ google_trends_score column exists")

    # Show stats
    print(f"\nStatistics:")
    print(f"  - Total tools: {len(df)}")
    print(f"  - Tools with Google Trends data (>0): {(df['google_trends_score'] > 0).sum()}")
    print(f"  - Tools without Google Trends data (=0): {(df['google_trends_score'] == 0).sum()}")
    print(f"  - Min value: {df['google_trends_score'].min():.1f}")
    print(f"  - Max value: {df['google_trends_score'].max():.1f}")
    print(f"  - Mean value (all tools): {df['google_trends_score'].mean():.1f}")
    print(f"  - Mean value (tools with data): {df[df['google_trends_score'] > 0]['google_trends_score'].mean():.1f}")

    # Show sample of tools with Google Trends data
    print(f"\nSample of tools WITH Google Trends data:")
    with_data = df[df['google_trends_score'] > 0][['Vendor Name', 'google_trends_score', 'popularity_score']].head(10)
    for idx, row in with_data.iterrows():
        print(f"  {row['Vendor Name']:30s}: trends={row['google_trends_score']:5.1f}, popularity={row['popularity_score']:5.1f}")

    # Show sample of tools without Google Trends data
    print(f"\nSample of tools WITHOUT Google Trends data:")
    without_data = df[df['google_trends_score'] == 0][['Vendor Name', 'google_trends_score', 'popularity_score']].head(5)
    for idx, row in without_data.iterrows():
        print(f"  {row['Vendor Name']:30s}: trends={row['google_trends_score']:5.1f}, popularity={row['popularity_score']:5.1f}")
else:
    print("\n❌ google_trends_score column NOT found!")
    print(f"\nAvailable columns: {list(df.columns)}")
