"""
Add Google Trends popularity scoring to all tools in the database.

Uses pytrends to fetch real search interest data and combines with other metrics
to create a comprehensive popularity score.

This will take ~15-20 minutes for 361 tools due to rate limiting.
"""

import pandas as pd
import time
from datetime import datetime
import json

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
    filled_fields = sum(1 for val in row.values() if val and str(val).strip() and str(val) != 'nan')
    completeness_score = min(filled_fields * 0.5, 15)
    score += completeness_score

    return round(score, 2)


def main():
    """Main execution."""

    print("="*80)
    print("GOOGLE TRENDS POPULARITY SCORING")
    print("="*80)

    # Check if pytrends is available
    if not PYTRENDS_AVAILABLE:
        print("\nERROR: pytrends library is required!")
        print("\nInstall with:")
        print("  pip install pytrends")
        return

    # Load database
    csv_file = 'merged_pref_top50_updated.csv'

    try:
        df = pd.read_csv(csv_file)
        print(f"\nLoaded: {csv_file}")
        print(f"Tools: {len(df)}")
    except FileNotFoundError:
        print(f"\nERROR: {csv_file} not found!")
        return

    # Add Google Trends scores
    print("\nFetching Google Trends data...")
    print("This will take ~15-20 minutes due to rate limiting")
    print("(Google limits to ~5 requests per minute)\n")

    df['google_trends_score'] = None

    for idx, row in df.iterrows():
        tool_name = row['Vendor Name']
        print(f"[{idx+1}/{len(df)}] {tool_name}...", end=' ')

        # Get trends score
        trends_score = get_google_trends_score(tool_name)
        df.at[idx, 'google_trends_score'] = trends_score

        print(f"Score: {trends_score}")

        # Rate limiting - Google allows ~5 requests per minute
        # Wait 12 seconds between requests to be safe
        if (idx + 1) % 5 == 0:
            print(f"  [Rate limit pause - {(idx+1)/len(df)*100:.1f}% complete]")
            time.sleep(15)
        else:
            time.sleep(3)

    # Calculate composite popularity scores
    print("\nCalculating composite popularity scores...")
    df['popularity_score'] = df.apply(calculate_composite_score, axis=1)

    # Sort by popularity (highest first)
    df_sorted = df.sort_values('popularity_score', ascending=False)

    # Show top 20
    print("\n" + "="*80)
    print("TOP 20 MOST POPULAR TOOLS")
    print("="*80)
    print(f"{'Rank':<6} {'Score':<8} {'Trends':<8} {'Tool Name':<40}")
    print("-"*80)
    for rank, (idx, row) in enumerate(df_sorted.head(20).iterrows(), 1):
        trends = row.get('google_trends_score', 0)
        print(f"{rank:<6} {row['popularity_score']:<8.1f} {trends:<8.1f} {row['Vendor Name']:<40}")

    # Save sorted version
    output_file = csv_file.replace('.csv', '_sorted.csv')
    df_sorted.to_csv(output_file, index=False)

    print(f"\n{'='*80}")
    print(f"SAVED!")
    print(f"{'='*80}")
    print(f"Sorted database: {output_file}")
    print(f"Total tools: {len(df_sorted)}")

    # Update the main file to use sorted version
    print(f"\nTo use this in your app:")
    print(f"1. Replace merged_pref_top50_updated.csv with the sorted version")
    print(f"   OR")
    print(f"2. Update index.html to use: {output_file}")

    # Save metrics for reference
    metrics_file = 'popularity_metrics.csv'
    df_sorted[['Vendor Name', 'google_trends_score', 'AI Powered',
               'Maturity Entry Level', 'popularity_score']].to_csv(metrics_file, index=False)
    print(f"\nMetrics saved to: {metrics_file}")

    # Statistics
    print(f"\n{'='*80}")
    print("STATISTICS")
    print(f"{'='*80}")
    print(f"Average Google Trends score: {df_sorted['google_trends_score'].mean():.2f}")
    print(f"Average popularity score: {df_sorted['popularity_score'].mean():.2f}")
    print(f"Highest popularity: {df_sorted['popularity_score'].max():.2f} ({df_sorted.iloc[0]['Vendor Name']})")
    print(f"Tools with trends data: {df_sorted['google_trends_score'].notna().sum()}")


if __name__ == "__main__":
    main()
