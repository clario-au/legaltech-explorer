"""
Quick collection on tools with known websites.
Demonstrates full pipeline with merge-ready output.
"""

import json
import pandas as pd
from datetime import datetime
from extract_tool_data import scrape_website, extract_with_ai, format_for_database

# Load tools with websites from cache
try:
    with open('tool_websites.json', 'r', encoding='utf-8') as f:
        tools_with_websites = json.load(f)
except FileNotFoundError:
    print("ERROR: tool_websites.json not found!")
    print("Please run assisted_website_finder.py or bulk_website_input.py first")
    exit(1)

print("="*80)
print("QUICK DATA COLLECTION")
print("="*80)
print(f"\nProcessing {len(tools_with_websites)} tools with known websites")
print("This will extract structured data from all collected websites\n")

results = []

for i, (tool_name, url) in enumerate(tools_with_websites.items(), 1):
    print(f"\n[{i}/{len(tools_with_websites)}] {tool_name}")
    print(f"URL: {url}")

    # Scrape
    content, success = scrape_website(url)
    if not success:
        print("  [SKIP] Failed to scrape")
        continue

    # Extract
    extracted = extract_with_ai(tool_name, url, content)
    if not extracted:
        print("  [SKIP] Failed to extract")
        continue

    # Format
    formatted = format_for_database(extracted, tool_name, url)
    results.append(formatted)

    print(f"  [SUCCESS]")

# Save results
if results:
    # Ensure exact database column order
    database_columns = [
        'Vendor Name', 'Vendor Overview', 'Product Name', 'Product Description',
        'Legal Functionality', 'Functionality Sub-Category', 'Main problem solved',
        'Primary User Segment', 'Maturity Entry Level', 'Regions Served',
        'AI Powered', 'AI Platform Type', 'Hosting Location', 'Pricing Model',
        'Demo / Proof of Concept Available', 'Adoption Level', 'Ease of Purchase',
        'Deployment Model', 'Industry Focus', 'Languages Supported', 'HQ',
        'Office Locations', 'Hosting Provider', 'ISO Certifications',
        'Security & Compliance Certifications', 'Approx. Price Range (AUD)',
        'Customer Reviews', 'Customer Feedback Rating', 'Vendor Website',
        'Vendor Contact Details'
    ]

    df = pd.DataFrame(results)

    # Add missing columns
    for col in database_columns:
        if col not in df.columns:
            df[col] = ""

    # Reorder
    df = df[database_columns]

    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = f"new_tools_{timestamp}.csv"

    df.to_csv(csv_file, index=False, encoding='utf-8')

    print(f"\n{'='*80}")
    print(f"COMPLETE!")
    print(f"{'='*80}")
    print(f"\nSaved to: {csv_file}")
    print(f"Tools extracted: {len(results)}")

    print(f"\n--- MERGE INSTRUCTIONS ---")
    print(f"To merge with existing database:")
    print(f"")
    print(f"import pandas as pd")
    print(f"")
    print(f"# Load files")
    print(f"existing = pd.read_csv('merged_pref_top50.csv')")
    print(f"new_tools = pd.read_csv('{csv_file}')")
    print(f"")
    print(f"# Merge")
    print(f"combined = pd.concat([existing, new_tools], ignore_index=True)")
    print(f"")
    print(f"# Remove duplicates (if any)")
    print(f"combined = combined.drop_duplicates(subset=['Vendor Name'], keep='first')")
    print(f"")
    print(f"# Save")
    print(f"combined.to_csv('merged_pref_top50_updated.csv', index=False)")
    print(f"print(f'Total tools: {{len(combined)}}')")

if __name__ == "__main__":
    pass
