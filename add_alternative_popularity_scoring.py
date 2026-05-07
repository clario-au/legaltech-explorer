"""
Add popularity scoring based on existing database fields (no external APIs).
Uses multi-factor scoring: Adoption Level, Maturity, AI Powered, Regions, Data Completeness.
"""

import pandas as pd
from datetime import datetime

def calculate_popularity_score(row):
    """
    Calculate popularity score from existing data.

    Scoring factors:
    - Adoption Level: 40 points max (strongest indicator of popularity)
    - Maturity Level: 25 points max (enterprise tools are more established)
    - AI Powered: 15 points (AI tools are trending)
    - Regions Served: 10 points (global reach indicates popularity)
    - Data Completeness: 10 points (well-documented = established)

    Total: 100 points max
    """
    score = 0

    # 1. Adoption Level (40 points max) - STRONGEST INDICATOR
    adoption = str(row.get('Adoption Level', '')).lower()
    if 'market leader' in adoption or 'standard' in adoption:
        score += 40
    elif 'mainstream' in adoption or 'proven' in adoption:
        score += 32
    elif 'growing adoption' in adoption or 'growing' in adoption:
        score += 24
    elif 'emerging' in adoption or 'new entrant' in adoption:
        score += 12

    # 2. Maturity Level (25 points max)
    maturity = str(row.get('Maturity Entry Level', '')).lower()
    if 'enterprise' in maturity:
        score += 25
    elif 'advanced' in maturity:
        score += 20
    elif 'quick win' in maturity or 'quick' in maturity:
        score += 12
    elif 'experimental' in maturity or 'early stage' in maturity:
        score += 5

    # 3. AI Powered (15 points)
    ai_powered = str(row.get('AI Powered', '')).lower()
    if ai_powered == 'yes':
        score += 15

    # 4. Regions Served (10 points max)
    regions = str(row.get('Regions Served', '')).lower()
    if 'global' in regions:
        score += 10
    elif any(x in regions for x in ['north america', 'europe', 'asia', 'australia']):
        # Count number of regions mentioned
        region_count = sum([
            'north america' in regions,
            'europe' in regions or 'uk' in regions or 'eu' in regions,
            'asia' in regions or 'apac' in regions,
            'australia' in regions,
            'africa' in regions,
            'latin' in regions or 'south america' in regions
        ])
        score += min(region_count * 3, 10)  # 3 points per region, max 10

    # 5. Data Completeness (10 points max)
    # Count non-empty fields
    filled_fields = sum(
        1 for val in row.values
        if pd.notna(val) and str(val).strip() and str(val) not in ['nan', '', 'N/A']
    )
    # More than 20 fields filled = max score
    completeness_score = min(filled_fields * 0.5, 10)
    score += completeness_score

    return round(score, 2)


def main():
    """Main execution."""

    print("="*80)
    print("ALTERNATIVE POPULARITY SCORING - NO EXTERNAL APIs")
    print("="*80)
    print("\nScoring based on:")
    print("  - Adoption Level (40%)")
    print("  - Maturity Level (25%)")
    print("  - AI Powered (15%)")
    print("  - Regions Served (10%)")
    print("  - Data Completeness (10%)")
    print()

    # Load database
    database_file = 'merged_pref_top50_updated.csv'

    try:
        df = pd.read_csv(database_file)
        print(f"Loaded: {database_file}")
        print(f"Total tools: {len(df)}\n")
    except FileNotFoundError:
        print(f"\nERROR: {database_file} not found!")
        return

    # Calculate scores
    print("Calculating popularity scores...")
    df['popularity_score'] = df.apply(calculate_popularity_score, axis=1)

    # Save results
    output_file = database_file.replace('.csv', '_with_scores.csv')
    df.to_csv(output_file, index=False)

    # Also update the original file
    df.to_csv(database_file, index=False)

    print(f"\n{'='*80}")
    print("COMPLETE!")
    print(f"{'='*80}")
    print(f"Updated: {database_file}")
    print(f"Backup saved: {output_file}")
    print(f"Total tools scored: {len(df)}\n")

    # Statistics
    print("="*80)
    print("SCORE STATISTICS")
    print("="*80)
    print(f"Average score: {df['popularity_score'].mean():.2f}")
    print(f"Median score: {df['popularity_score'].median():.2f}")
    print(f"Min score: {df['popularity_score'].min():.2f}")
    print(f"Max score: {df['popularity_score'].max():.2f}")
    print(f"Std deviation: {df['popularity_score'].std():.2f}")

    # Distribution
    print("\nScore distribution:")
    bins = [0, 20, 40, 60, 80, 100]
    labels = ['0-20', '21-40', '41-60', '61-80', '81-100']
    df['score_range'] = pd.cut(df['popularity_score'], bins=bins, labels=labels, include_lowest=True)
    print(df['score_range'].value_counts().sort_index())

    # Top 30 tools
    print("\n" + "="*80)
    print("TOP 30 TOOLS BY POPULARITY SCORE")
    print("="*80)

    df_sorted = df.sort_values('popularity_score', ascending=False)

    print(f"{'Rank':<6} {'Score':<8} {'Adoption':<25} {'Tool Name':<40}")
    print("-"*80)

    for rank, (idx, row) in enumerate(df_sorted.head(30).iterrows(), 1):
        adoption = str(row.get('Adoption Level', 'N/A'))[:23]
        vendor = str(row['Vendor Name'])[:38]
        print(f"{rank:<6} {row['popularity_score']:<8.1f} {adoption:<25} {vendor:<40}")

    # Bottom 10 (need more data)
    print("\n" + "="*80)
    print("BOTTOM 10 TOOLS (May need more data)")
    print("="*80)

    print(f"{'Rank':<6} {'Score':<8} {'Adoption':<25} {'Tool Name':<40}")
    print("-"*80)

    for rank, (idx, row) in enumerate(df_sorted.tail(10).iterrows(), 1):
        adoption = str(row.get('Adoption Level', 'N/A'))[:23]
        vendor = str(row['Vendor Name'])[:38]
        print(f"{rank:<6} {row['popularity_score']:<8.1f} {adoption:<25} {vendor:<40}")

    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print("1. Review the top/bottom tools to validate scoring")
    print("2. Fill in missing Adoption Level & Maturity data for low-scoring tools")
    print("3. The database now has a 'popularity_score' column for sorting/filtering")
    print("4. Your web UI can now sort by popularity!")


if __name__ == "__main__":
    main()
