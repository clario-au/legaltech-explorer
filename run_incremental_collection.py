"""
Incremental data collection - only processes NEW tools not in database.
Compares tool_websites.json against existing database to find new additions.
"""

import json
import pandas as pd
from datetime import datetime
from extract_tool_data import scrape_website, extract_with_ai, format_for_database

# Load existing database to find what tools we already have
try:
    existing_df = pd.read_csv('merged_pref_top50_updated.csv')
    existing_tools = set(existing_df['Vendor Name'].tolist())
    print(f"Loaded existing database: {len(existing_tools)} tools")
except FileNotFoundError:
    print("ERROR: merged_pref_top50_updated.csv not found!")
    exit(1)

# Load tools with websites from cache
try:
    with open('tool_websites.json', 'r', encoding='utf-8') as f:
        all_tools_with_websites = json.load(f)
    print(f"Loaded website cache: {len(all_tools_with_websites)} tools")
except FileNotFoundError:
    print("ERROR: tool_websites.json not found!")
    exit(1)

# Find NEW tools (in website cache but NOT in database)
new_tools = {name: url for name, url in all_tools_with_websites.items()
             if name not in existing_tools}

print("="*80)
print("INCREMENTAL DATA COLLECTION")
print("="*80)
print(f"\nFound {len(new_tools)} NEW tools to process")
print(f"(Skipping {len(existing_tools)} tools already in database)\n")

if len(new_tools) == 0:
    print("No new tools to process. All tools in website cache are already in database.")
    exit(0)

# Show what we'll process
print("New tools to process:")
for i, name in enumerate(list(new_tools.keys())[:10], 1):
    print(f"  {i}. {name}")
if len(new_tools) > 10:
    print(f"  ... and {len(new_tools) - 10} more")
print()
print("Starting processing...")

results = []

for i, (tool_name, url) in enumerate(new_tools.items(), 1):
    print(f"\n[{i}/{len(new_tools)}] {tool_name}")
    print(f"URL: {url}")

    # Scrape
    print("  > Scraping website...")
    html_content = scrape_website(url)

    if not html_content:
        print("  X Failed to scrape website")
        continue

    print(f"  OK Scraped {len(html_content)} chars")

    # Extract with AI
    print("  > Extracting data with AI...")
    extracted_data = extract_with_ai(tool_name, url, html_content)

    if not extracted_data:
        print("  X Failed to extract data")
        continue

    print("  OK Extracted data")

    # Format for database
    formatted = format_for_database(extracted_data, tool_name, url)
    results.append(formatted)

    # Progress save every 5 tools
    if len(results) % 5 == 0:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_file = f'new_tools_incremental_{timestamp}_partial.csv'
        pd.DataFrame(results).to_csv(temp_file, index=False)
        print(f"  [PROGRESS SAVED - {len(results)} tools extracted]")

# Final save
print("\n" + "="*80)
print("COMPLETE")
print("="*80)

if results:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f'new_tools_incremental_{timestamp}.csv'

    df = pd.DataFrame(results)
    df.to_csv(output_file, index=False)

    print(f"\n[OK] Successfully extracted {len(results)} new tools")
    print(f"[OK] Saved to: {output_file}")
    print(f"\nNext step:")
    print(f"  Run merge script to add these {len(results)} tools to the main database")
else:
    print("\nNo tools were successfully extracted.")
