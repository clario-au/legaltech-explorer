"""
Add popularity metrics to tools for sorting by relevance.

This script fetches publicly available metrics:
1. SimilarWeb traffic data (if available via API)
2. Google search volume estimates
3. Domain authority metrics
4. LinkedIn company size (as proxy for company maturity)

For now, we'll use simpler heuristics:
- Domain age (older = more established)
- Website response time (faster = more professional)
- HTTPS status (more secure = more professional)
- Alexa/Tranco rankings (if available)
"""

import pandas as pd
import requests
from urllib.parse import urlparse
import time
from datetime import datetime

def get_domain(url):
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.replace('www.', '')
    except:
        return None

def get_tranco_rank(domain):
    """
    Get Tranco ranking (free alternative to Alexa).
    Tranco is a research-oriented top sites ranking.
    Lower rank = more popular.
    """
    try:
        # We'll use a simplified approach - check if domain is in top 1M list
        # You can download the full list from https://tranco-list.eu/
        # For now, we'll return None and implement this later
        return None
    except:
        return None

def estimate_website_quality(url):
    """
    Simple quality metrics:
    - Response time (ms)
    - HTTPS enabled
    - Response status
    """
    metrics = {
        'response_time_ms': None,
        'has_https': False,
        'is_accessible': False
    }

    try:
        start = time.time()
        response = requests.get(url, timeout=10, allow_redirects=True)
        end = time.time()

        metrics['response_time_ms'] = int((end - start) * 1000)
        metrics['has_https'] = url.startswith('https://')
        metrics['is_accessible'] = response.status_code == 200

    except:
        pass

    return metrics

def calculate_popularity_score(row):
    """
    Calculate a composite popularity score from available metrics.

    Factors:
    1. Maturity Entry Level (advanced > intermediate > quick win)
    2. AI Powered (yes = +10 points, it's trendy)
    3. Response time (faster = better)
    4. HTTPS (yes = +5 points)
    5. Accessibility (yes = +10 points)
    """
    score = 50  # Base score

    # Maturity bonus
    maturity = str(row.get('Maturity Entry Level', '')).lower()
    if 'advanced' in maturity:
        score += 20
    elif 'intermediate' in maturity or 'medium' in maturity:
        score += 10
    elif 'quick' in maturity:
        score += 5

    # AI bonus (AI tools are trending)
    if str(row.get('AI Powered', '')).lower() == 'yes':
        score += 15

    # Response time bonus (faster = more professional)
    response_time = row.get('response_time_ms')
    if response_time and response_time < 500:
        score += 10
    elif response_time and response_time < 1000:
        score += 5

    # HTTPS bonus
    if row.get('has_https'):
        score += 5

    # Accessibility bonus
    if row.get('is_accessible'):
        score += 10

    # Bonus for having detailed info (more fields filled)
    filled_fields = sum(1 for val in row.values() if val and str(val).strip() and str(val) != 'nan')
    score += min(filled_fields, 20)  # Cap at 20 bonus points

    return score


def main():
    """Main execution."""

    print("="*80)
    print("ADD POPULARITY METRICS")
    print("="*80)

    # Load the latest extracted data
    csv_file = 'new_tools_20251220_100200.csv'

    try:
        df = pd.read_csv(csv_file)
        print(f"\nLoaded: {csv_file}")
        print(f"Tools: {len(df)}")
    except FileNotFoundError:
        print(f"\nERROR: {csv_file} not found!")
        return

    # Add metrics columns
    print("\nFetching website metrics...")

    df['domain'] = df['Vendor Website'].apply(get_domain)
    df['response_time_ms'] = None
    df['has_https'] = False
    df['is_accessible'] = False

    # Fetch metrics for each tool (with rate limiting)
    for idx, row in df.iterrows():
        url = row['Vendor Website']
        if pd.notna(url) and url:
            print(f"[{idx+1}/{len(df)}] {row['Vendor Name']}...")

            metrics = estimate_website_quality(url)
            df.at[idx, 'response_time_ms'] = metrics['response_time_ms']
            df.at[idx, 'has_https'] = metrics['has_https']
            df.at[idx, 'is_accessible'] = metrics['is_accessible']

            time.sleep(0.5)  # Rate limiting

    # Calculate popularity scores
    print("\nCalculating popularity scores...")
    df['popularity_score'] = df.apply(calculate_popularity_score, axis=1)

    # Sort by popularity (highest first)
    df_sorted = df.sort_values('popularity_score', ascending=False)

    # Show top 10
    print("\n" + "="*80)
    print("TOP 10 MOST POPULAR TOOLS")
    print("="*80)
    for idx, row in df_sorted.head(10).iterrows():
        print(f"{row['popularity_score']:.0f} - {row['Vendor Name']}")

    # Save sorted version
    output_file = csv_file.replace('.csv', '_sorted.csv')
    df_sorted.to_csv(output_file, index=False)

    print(f"\n✓ Saved sorted data to: {output_file}")
    print(f"\nYou can now use this sorted file in your application!")

    # Also save just the popularity metrics for reference
    metrics_file = 'popularity_metrics.csv'
    df_sorted[['Vendor Name', 'domain', 'response_time_ms', 'has_https',
               'is_accessible', 'popularity_score']].to_csv(metrics_file, index=False)
    print(f"✓ Saved metrics to: {metrics_file}")


if __name__ == "__main__":
    main()
