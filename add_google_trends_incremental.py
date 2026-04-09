"""
Add Google Trends popularity scoring to ONLY newly added tools.
Compares against existing database to identify new tools.
"""

import pandas as pd
import time
from datetime import datetime

# Check if pytrends is installed
try:
    from pytrends.request import TrendReq
    PYTRENDS_AVAILABLE = True
except ImportError:
    PYTRENDS_AVAILABLE = False
    print("WARNING: pytrends not installed. Install with: pip install pytrends")


def get_google_trends_score(tool_name, retry_count=3):
    """
    Get relative search interest from Google Trends.
    Returns a score 0-100 (100 = peak popularity).
    """
    if not PYTRENDS_AVAILABLE:
        return None

    try:
        pytrends = TrendReq(hl='en-US', tz=360)

        # Build query - try tool name
        kw_list = [tool_name]

        # Get interest over time (last 12 months)
        pytrends.build_payload(kw_list, cat=0, timeframe='today 12-m', geo='', gprop='')
        interest_df = pytrends.interest_over_time()

        if interest_df.empty or tool_name not in interest_df.columns:
            return 0

        # Calculate average interest
        avg_interest = interest_df[tool_name].mean()
        return round(avg_interest, 2)

    except Exception as e:
        if retry_count > 0:
            time.sleep(5)  # Wait before retry
            return get_google_trends_score(tool_name, retry_count - 1)
        print(f"  [WARNING] Failed to get trends for {tool_name}: {str(e)[:50]}")
        return 0


def calculate_composite_score(row):
    """
    Calculate final popularity score combining multiple factors.

    Weights:
    - Google Trends: 50%
    - AI Powered: 15%
    - Maturity Level: 20%
    - Data Completeness: 15%
    """
    score = 0

    # Google Trends (0-100, weight 50%)
    trends_score = row.get('google_trends_score', 0)
    if pd.notna(trends_score) and trends_score > 0:
        score += trends_score * 0.5

    # AI Powered bonus (15 points)
    if str(row.get('AI Powered', '')).lower() == 'yes':
        score += 15

    # Maturity bonus (20 points max)
    maturity = str(row.get('Maturity Entry Level', '')).lower()
    if 'advanced' in maturity:
        score += 20
    elif 'intermediate' in maturity or 'medium' in maturity:
        score += 12
    elif 'quick' in maturity:
        score += 8

    # Data completeness (15 points max)
    filled_fields = sum(1 for val in row.values if pd.notna(val) and str(val).strip() and str(val) != 'nan')
    completeness_score = min(filled_fields * 0.5, 15)
    score += completeness_score

    return round(score, 2)


def main():
    """Main execution."""

    print("="*80)
    print("INCREMENTAL GOOGLE TRENDS POPULARITY SCORING")
    print("="*80)

    # Check if pytrends is available
    if not PYTRENDS_AVAILABLE:
        print("\nERROR: pytrends library is required!")
        print("\nInstall with:")
        print("  pip install pytrends")
        return

    # Load the newly extracted incremental data
    # Find the latest incremental file
    import glob
    incremental_files = glob.glob('new_tools_incremental_*.csv')
    if not incremental_files:
        print("\nERROR: No incremental files found!")
        print("Please run run_incremental_collection.py first")
        return

    latest_file = sorted(incremental_files)[-1]

    try:
        df_new = pd.read_csv(latest_file)
        print(f"\nLoaded: {latest_file}")
        print(f"New tools: {len(df_new)}")
    except FileNotFoundError:
        print(f"\nERROR: {latest_file} not found!")
        return

    # Add Google Trends scores to new tools only
    print("\nFetching Google Trends data for NEW tools only...")
    print(f"This will take ~{len(df_new) * 3 / 60:.0f} minutes due to rate limiting")
    print("(Google limits to ~5 requests per minute)\n")

    df_new['google_trends_score'] = None

    for idx, row in df_new.iterrows():
        tool_name = row['Vendor Name']
        print(f"[{idx+1}/{len(df_new)}] {tool_name}...", end=' ')

        # Get trends score
        trends_score = get_google_trends_score(tool_name)
        df_new.at[idx, 'google_trends_score'] = trends_score

        print(f"Score: {trends_score}")

        # Rate limiting - Google allows ~5 requests per minute
        # Wait 12 seconds between requests to be safe
        if (idx + 1) % 5 == 0:
            print(f"  [Rate limit pause - {(idx+1)/len(df_new)*100:.1f}% complete]")
            time.sleep(15)
        else:
            time.sleep(3)

    # Calculate composite popularity scores
    print("\nCalculating composite popularity scores...")
    df_new['popularity_score'] = df_new.apply(calculate_composite_score, axis=1)

    # Save the updated incremental file with scores
    output_file = latest_file.replace('.csv', '_scored.csv')
    df_new.to_csv(output_file, index=False)

    print(f"\n{'='*80}")
    print(f"SAVED!")
    print(f"{'='*80}")
    print(f"Scored incremental data: {output_file}")
    print(f"Total new tools: {len(df_new)}")

    # Show top 10 new tools
    print("\n" + "="*80)
    print("TOP 10 NEW TOOLS BY POPULARITY")
    print("="*80)
    df_sorted = df_new.sort_values('popularity_score', ascending=False)
    print(f"{'Rank':<6} {'Score':<8} {'Trends':<8} {'Tool Name':<40}")
    print("-"*80)
    for rank, (idx, row) in enumerate(df_sorted.head(10).iterrows(), 1):
        trends = row.get('google_trends_score', 0)
        print(f"{rank:<6} {row['popularity_score']:<8.1f} {trends:<8.1f} {row['Vendor Name']:<40}")

    print(f"\n{'='*80}")
    print("NEXT STEP")
    print(f"{'='*80}")
    print(f"Merge this scored data with the main database:")
    print(f"  merged_pref_top50_updated.csv (361 tools)")
    print(f"  + {output_file} ({len(df_new)} tools)")
    print(f"  = ~{361 + len(df_new)} total tools")


if __name__ == "__main__":
    main()
