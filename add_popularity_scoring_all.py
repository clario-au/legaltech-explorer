"""
Add Google Trends popularity scoring to ALL tools in the database.
Handles rate limiting with conservative delays and saves progress frequently.
"""

import pandas as pd
import time
from datetime import datetime
import os
import sys

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

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
        pytrends = TrendReq(hl='en-US', tz=360, timeout=(10, 25))

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
            print(f"  [RETRY] Waiting 10s before retry...")
            time.sleep(10)  # Wait before retry
            return get_google_trends_score(tool_name, retry_count - 1)
        print(f"  [WARNING] Failed to get trends for {tool_name}: {str(e)[:100]}")
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
    if 'advanced' in maturity or 'enterprise' in maturity:
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
    print("GOOGLE TRENDS POPULARITY SCORING - ALL TOOLS")
    print("="*80)

    # Check if pytrends is available
    if not PYTRENDS_AVAILABLE:
        print("\nERROR: pytrends library is required!")
        print("\nInstall with:")
        print("  pip install pytrends")
        return

    # Load the main database
    database_file = 'merged_pref_top50_updated.csv'

    try:
        df = pd.read_csv(database_file)
        print(f"\nLoaded: {database_file}")
        print(f"Total tools: {len(df)}")
    except FileNotFoundError:
        print(f"\nERROR: {database_file} not found!")
        return

    # Check if we're resuming from a previous run
    progress_file = 'scoring_progress.csv'
    start_index = 0

    if os.path.exists(progress_file):
        print(f"\n[FOUND] Previous progress file: {progress_file}")
        print("[AUTO] Resuming from where we left off...")

        df_progress = pd.read_csv(progress_file)
        # Merge progress into main dataframe
        df = df_progress
        # Find first row without google_trends_score
        scored_mask = df['google_trends_score'].notna()
        start_index = scored_mask.sum()
        print(f"[OK] Resuming from tool #{start_index + 1}")
    else:
        # Initialize scoring columns
        df['google_trends_score'] = None
        df['popularity_score'] = None

    # Calculate time estimate
    remaining = len(df) - start_index
    estimated_minutes = (remaining * 15) / 60  # 15 seconds per tool

    print(f"\nTools to score: {remaining}")
    print(f"Estimated time: {estimated_minutes:.0f} minutes (~{estimated_minutes/60:.1f} hours)")
    print("Rate limiting: 15 seconds between requests (safe for Google)")
    print("Progress saved every 10 tools")
    print("\n[AUTO-STARTING] Processing all tools...")

    print("\n" + "="*80)
    print("STARTING GOOGLE TRENDS SCORING")
    print("="*80)

    scored_count = 0

    for idx in range(start_index, len(df)):
        row = df.iloc[idx]
        tool_name = row['Vendor Name']

        print(f"\n[{idx+1}/{len(df)}] {tool_name}", flush=True)

        # Get trends score
        trends_score = get_google_trends_score(tool_name)
        df.at[idx, 'google_trends_score'] = trends_score

        print(f"  Trends Score: {trends_score}", flush=True)

        # Calculate composite score immediately
        df.at[idx, 'popularity_score'] = calculate_composite_score(df.iloc[idx])

        scored_count += 1

        # Save progress every 10 tools
        if scored_count % 10 == 0:
            df.to_csv(progress_file, index=False)
            print(f"  [PROGRESS SAVED - {idx+1}/{len(df)} tools scored ({(idx+1)/len(df)*100:.1f}%)]")

        # Rate limiting - wait 15 seconds between requests (4 per minute, very safe)
        if idx < len(df) - 1:  # Don't wait after the last one
            print(f"  [Waiting 15s for rate limit...]")
            time.sleep(15)

    # Calculate all composite scores
    print("\n" + "="*80)
    print("CALCULATING FINAL COMPOSITE SCORES")
    print("="*80)

    df['popularity_score'] = df.apply(calculate_composite_score, axis=1)

    # Save final result
    output_file = database_file.replace('.csv', '_scored.csv')
    df.to_csv(output_file, index=False)

    # Also overwrite the original
    df.to_csv(database_file, index=False)

    print(f"\n{'='*80}")
    print(f"COMPLETE!")
    print(f"{'='*80}")
    print(f"Scored file: {output_file}")
    print(f"Updated original: {database_file}")
    print(f"Total tools scored: {len(df)}")

    # Show top 20 by popularity
    print("\n" + "="*80)
    print("TOP 20 TOOLS BY POPULARITY SCORE")
    print("="*80)
    df_sorted = df.sort_values('popularity_score', ascending=False)
    print(f"{'Rank':<6} {'Score':<8} {'Trends':<8} {'Tool Name':<40}")
    print("-"*80)
    for rank, (idx, row) in enumerate(df_sorted.head(20).iterrows(), 1):
        trends = row.get('google_trends_score', 0)
        print(f"{rank:<6} {row['popularity_score']:<8.1f} {trends:<8.1f} {row['Vendor Name']:<40}")

    # Cleanup progress file
    if os.path.exists(progress_file):
        os.remove(progress_file)
        print(f"\n[OK] Removed progress file")


if __name__ == "__main__":
    main()
