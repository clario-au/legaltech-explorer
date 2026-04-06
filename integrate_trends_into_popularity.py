"""
Integrate Google Trends data into popularity scoring.

This script:
1. Loads the most recent Trends results
2. Normalizes Trends scores appropriately
3. Integrates into existing popularity scoring
4. Updates the database and HTML
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path
from datetime import datetime
import json

# Fix UTF-8 encoding on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# ============================================================================
# CONFIGURATION
# ============================================================================

POPULARITY_WEIGHTS = {
    "adoption_level": 0.30,      # Reduced from 0.40
    "maturity": 0.20,            # Reduced from 0.25
    "ai_powered": 0.10,          # Reduced from 0.15
    "regions": 0.08,             # Reduced from 0.10
    "completeness": 0.07,        # Reduced from 0.10
    "google_trends": 0.25        # NEW - significant weight for market interest
}

# Ensure weights sum to 1.0
assert abs(sum(POPULARITY_WEIGHTS.values()) - 1.0) < 0.001, "Weights must sum to 1.0"

# ============================================================================
# LOAD TRENDS DATA
# ============================================================================

def find_latest_trends_file():
    """Find the most recent Trends results file."""
    trends_files = list(Path('.').glob('google_trends_results_*.csv'))

    if not trends_files:
        print("❌ No Trends results files found!")
        print("   Run google_trends_collector.py first")
        return None

    # Sort by timestamp in filename
    latest = sorted(trends_files)[-1]
    print(f"📊 Found Trends data: {latest}")
    return latest

def load_trends_data(trends_file):
    """Load and validate Trends data."""
    df = pd.read_csv(trends_file)

    print(f"   Loaded {len(df)} tools")
    print(f"   Successful: {sum(df['status'] == 'success')}")
    print(f"   No data: {sum(df['status'] == 'no_data')}")
    print(f"   Failed: {sum(df['status'] == 'failed')}")

    return df

# ============================================================================
# NORMALIZE TRENDS SCORES
# ============================================================================

def normalize_trends_scores(trends_df):
    """
    Normalize Trends scores to 0-100 scale.

    Important: Trends data is already 0-100 within the timeframe,
    but we need to handle:
    - Missing/sparse data (NaN or None)
    - Relative scaling across all tools
    """
    print("\n📐 Normalizing Trends scores...")

    # Extract numeric scores, handling missing data
    scores = trends_df['trends_score'].copy()
    scores = pd.to_numeric(scores, errors='coerce')

    # Count missing
    missing_count = scores.isna().sum()
    valid_count = (~scores.isna()).sum()

    print(f"   Valid scores: {valid_count}")
    print(f"   Missing scores: {missing_count}")

    if valid_count == 0:
        print("   ⚠️  No valid Trends scores - all will be set to 50.0 (neutral)")
        trends_df['trends_normalized'] = 50.0
        return trends_df

    # Get stats on valid scores
    valid_scores = scores[~scores.isna()]
    print(f"   Score range: {valid_scores.min():.2f} - {valid_scores.max():.2f}")
    print(f"   Mean: {valid_scores.mean():.2f}, Median: {valid_scores.median():.2f}")

    # Normalize to 0-100 scale
    # Option 1: Use as-is (Trends is already 0-100)
    # Option 2: Re-scale based on actual min/max in our dataset
    # Using Option 2 for better distribution:

    min_score = valid_scores.min()
    max_score = valid_scores.max()

    if max_score - min_score < 1:  # All scores nearly identical
        normalized = 50.0  # Middle value
    else:
        # Linear normalization to 0-100
        normalized = ((scores - min_score) / (max_score - min_score)) * 100

    # Fill missing with median of valid scores (conservative approach)
    median_normalized = normalized[~normalized.isna()].median() if valid_count > 0 else 50.0
    normalized = normalized.fillna(median_normalized)

    trends_df['trends_normalized'] = normalized

    print(f"   Normalized range: {normalized.min():.2f} - {normalized.max():.2f}")
    print(f"   Missing values filled with: {median_normalized:.2f}")

    return trends_df

# ============================================================================
# CALCULATE ENHANCED POPULARITY SCORE
# ============================================================================

def calculate_component_score(value, value_type):
    """Calculate component score (0-100) based on value type."""
    if pd.isna(value) or value == '':
        return 0.0

    if value_type == 'adoption_level':
        mapping = {
            'Widely Adopted': 100,
            'Established': 75,
            'Growing': 50,
            'Emerging': 25,
            'Niche': 10
        }
        return mapping.get(value, 0)

    elif value_type == 'maturity':
        mapping = {
            'Mature': 100,
            'Established': 75,
            'Growing': 50,
            'Early Stage': 25
        }
        return mapping.get(value, 0)

    elif value_type == 'ai_powered':
        return 100 if value in ['Yes', 'Core Feature', True] else 0

    elif value_type == 'regions':
        if pd.isna(value):
            return 0
        count = len(str(value).split(',')) if ',' in str(value) else (1 if value else 0)
        # More regions = higher score, capped at 100
        return min(count * 20, 100)

    elif value_type == 'completeness':
        # Calculate based on how many fields are filled
        return value * 100 if isinstance(value, (int, float)) else 0

    return 0.0

def calculate_enhanced_popularity(df, trends_df):
    """Calculate enhanced popularity scores with Trends data."""
    print("\n🎯 Calculating enhanced popularity scores...")

    # Merge Trends data
    merged = df.merge(
        trends_df[['Vendor Name', 'trends_normalized']],
        on='Vendor Name',
        how='left'
    )

    # Fill missing Trends scores with median
    median_trends = trends_df['trends_normalized'].median()
    merged['trends_normalized'] = merged['trends_normalized'].fillna(median_trends)

    print(f"   Using median Trends score {median_trends:.2f} for tools without data")

    # Calculate component scores
    adoption_scores = merged['Adoption Level'].apply(
        lambda x: calculate_component_score(x, 'adoption_level')
    )

    maturity_scores = merged['Maturity'].apply(
        lambda x: calculate_component_score(x, 'maturity')
    )

    ai_scores = merged['AI-Powered'].apply(
        lambda x: calculate_component_score(x, 'ai_powered')
    )

    region_scores = merged['Region'].apply(
        lambda x: calculate_component_score(x, 'regions')
    )

    # Completeness score
    required_fields = ['Vendor Name', 'Product Name', 'Description', 'Website', 'Category']
    completeness_scores = merged[required_fields].notna().sum(axis=1) / len(required_fields)
    completeness_scores = completeness_scores * 100

    # Trends scores (already normalized)
    trends_scores = merged['trends_normalized']

    # Combined weighted score
    popularity_score = (
        adoption_scores * POPULARITY_WEIGHTS['adoption_level'] +
        maturity_scores * POPULARITY_WEIGHTS['maturity'] +
        ai_scores * POPULARITY_WEIGHTS['ai_powered'] +
        region_scores * POPULARITY_WEIGHTS['regions'] +
        completeness_scores * POPULARITY_WEIGHTS['completeness'] +
        trends_scores * POPULARITY_WEIGHTS['google_trends']
    )

    merged['popularity_score'] = popularity_score.round(2)

    # Add component scores for debugging
    merged['_adoption_component'] = (adoption_scores * POPULARITY_WEIGHTS['adoption_level']).round(2)
    merged['_maturity_component'] = (maturity_scores * POPULARITY_WEIGHTS['maturity']).round(2)
    merged['_ai_component'] = (ai_scores * POPULARITY_WEIGHTS['ai_powered']).round(2)
    merged['_regions_component'] = (region_scores * POPULARITY_WEIGHTS['regions']).round(2)
    merged['_completeness_component'] = (completeness_scores * POPULARITY_WEIGHTS['completeness']).round(2)
    merged['_trends_component'] = (trends_scores * POPULARITY_WEIGHTS['google_trends']).round(2)

    print(f"   Popularity score range: {popularity_score.min():.2f} - {popularity_score.max():.2f}")
    print(f"   Mean: {popularity_score.mean():.2f}, Median: {popularity_score.median():.2f}")

    return merged

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution."""

    print("=" * 80)
    print("INTEGRATE GOOGLE TRENDS INTO POPULARITY SCORING")
    print("=" * 80)

    # Find latest Trends data
    trends_file = find_latest_trends_file()
    if not trends_file:
        return

    # Load Trends data
    trends_df = load_trends_data(trends_file)

    # Normalize Trends scores
    trends_df = normalize_trends_scores(trends_df)

    # Load main database
    db_file = Path('merged_pref_top50_updated.csv')
    if not db_file.exists():
        print(f"❌ Database not found: {db_file}")
        return

    df = pd.read_csv(db_file)
    print(f"\n📂 Loaded database: {len(df)} tools")

    # Calculate enhanced popularity
    enhanced_df = calculate_enhanced_popularity(df, trends_df)

    # Save enhanced database
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"merged_pref_top50_updated_with_trends_{timestamp}.csv"

    # Drop debug columns before saving
    debug_cols = [col for col in enhanced_df.columns if col.startswith('_')]
    save_df = enhanced_df.drop(columns=debug_cols + ['trends_normalized'])

    save_df.to_csv(output_file, index=False)

    # Also update the main file
    save_df.to_csv(db_file, index=False)

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\nPopularity score composition:")
    for component, weight in POPULARITY_WEIGHTS.items():
        print(f"  {component:20s}: {weight*100:5.1f}%")

    print(f"\nTop 10 tools by enhanced popularity:")
    top_10 = enhanced_df.nlargest(10, 'popularity_score')[
        ['Vendor Name', 'popularity_score', '_trends_component', '_adoption_component']
    ]
    for idx, row in top_10.iterrows():
        print(f"  {row['Vendor Name']:30s} - Score: {row['popularity_score']:5.1f} "
              f"(Trends: {row['_trends_component']:4.1f}, Adoption: {row['_adoption_component']:4.1f})")

    print(f"\n✓ Enhanced database saved to:")
    print(f"  - {output_file}")
    print(f"  - {db_file} (updated)")

    print(f"\n📋 Next step: Run update_html_data.py to update the web UI")

if __name__ == "__main__":
    main()
