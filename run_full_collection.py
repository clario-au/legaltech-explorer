"""
Full data collection pipeline for Priority 1 tools.

This script:
1. Loads Priority 1 tools (simple names)
2. Finds websites using DuckDuckGo search
3. Extracts data from each website
4. Saves to CSV in exact database format for easy merging

Output will be merge-ready with merged_pref_top50.csv
"""

import os
import json
import time
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime
from extract_tool_data import scrape_website, extract_with_ai, format_for_database
from find_websites_auto import search_duckduckgo, find_likely_official_website
import re

load_dotenv()

def load_priority_1_tools():
    """Load Priority 1 (simple name) tools from file."""
    tools = []
    with open('tools_priority_1_easy.txt', 'r', encoding='utf-8') as f:
        for line in f:
            match = re.match(r'^\d+\.\s+(.+)$', line.strip())
            if match:
                tools.append(match.group(1))
    return tools


def find_or_load_website(tool_name: str, website_cache: dict, auto_mode: bool = True) -> str:
    """
    Find website for a tool, using cache if available.

    Args:
        tool_name: Tool name
        website_cache: Dict of already-found websites
        auto_mode: If True, automatically select best match. If False, skip.

    Returns:
        Website URL or empty string
    """
    # Check cache first
    if tool_name in website_cache:
        return website_cache[tool_name]

    # Try to find website
    print(f"\n  Searching for website...")

    url = find_likely_official_website(tool_name)

    if url and auto_mode:
        print(f"  Found: {url}")
        website_cache[tool_name] = url
        return url
    elif url and not auto_mode:
        print(f"  Suggested: {url}")
        print(f"  (Skipping - manual mode)")
        return ""
    else:
        print(f"  No website found")
        return ""


def process_all_tools(tools: list, start_index: int = 0, batch_size: int = None, auto_find_websites: bool = True):
    """
    Process all tools through the pipeline.

    Args:
        tools: List of tool names
        start_index: Index to start from (for resuming)
        batch_size: Number of tools to process (None = all)
        auto_find_websites: If True, automatically find websites. If False, skip tools without known websites.

    Returns:
        List of extracted data dictionaries
    """

    # Load website cache
    website_cache = {}
    try:
        with open('tool_websites.json', 'r', encoding='utf-8') as f:
            website_cache = json.load(f)
        print(f"Loaded {len(website_cache)} cached websites")
    except FileNotFoundError:
        print("No website cache found - will search for all tools")

    # Determine batch
    if batch_size:
        tools_to_process = tools[start_index:start_index + batch_size]
    else:
        tools_to_process = tools[start_index:]

    print(f"\nProcessing {len(tools_to_process)} tools (starting from index {start_index})")
    print(f"Auto-find websites: {auto_find_websites}")

    results = []
    successful = 0
    failed_scrape = 0
    failed_extraction = 0
    no_website = 0

    for i, tool_name in enumerate(tools_to_process, 1):
        print(f"\n{'='*80}")
        print(f"[{start_index + i}/{start_index + len(tools_to_process)}] {tool_name}")
        print(f"{'='*80}")

        # Find website
        url = find_or_load_website(tool_name, website_cache, auto_mode=auto_find_websites)

        if not url:
            print(f"  [SKIP] No website found")
            no_website += 1
            results.append({
                "Vendor Name": tool_name,
                "_status": "no_website"
            })
            continue

        # Scrape website
        print(f"  Scraping {url}...")
        content, success = scrape_website(url)

        if not success or not content:
            print(f"  [FAILED] Could not scrape")
            failed_scrape += 1
            results.append({
                "Vendor Name": tool_name,
                "Vendor Website": url,
                "_status": "scrape_failed"
            })
            continue

        print(f"  [OK] Scraped {len(content)} characters")

        # Extract with AI
        print(f"  Extracting data...")
        extracted = extract_with_ai(tool_name, url, content)

        if not extracted:
            print(f"  [FAILED] Extraction failed")
            failed_extraction += 1
            results.append({
                "Vendor Name": tool_name,
                "Vendor Website": url,
                "_status": "extraction_failed"
            })
            continue

        # Format for database
        formatted = format_for_database(extracted, tool_name, url)
        formatted["_status"] = "success"

        results.append(formatted)
        successful += 1

        print(f"  [SUCCESS] Extracted {len([v for v in extracted.values() if v])} fields")

        # Rate limiting
        time.sleep(2)

        # Save progress periodically
        if i % 10 == 0:
            save_progress(results, start_index + i)
            save_website_cache(website_cache)

    # Final save
    save_website_cache(website_cache)

    # Print summary
    print(f"\n{'='*80}")
    print(f"BATCH COMPLETE")
    print(f"{'='*80}")
    print(f"Processed: {len(tools_to_process)}")
    print(f"Successful: {successful}")
    print(f"Failed - No website: {no_website}")
    print(f"Failed - Scrape error: {failed_scrape}")
    print(f"Failed - Extraction error: {failed_extraction}")
    print(f"Success rate: {successful}/{len(tools_to_process)} ({successful/len(tools_to_process)*100:.1f}%)")

    return results


def save_progress(results: list, count: int):
    """Save progress to JSON file."""
    with open('collection_progress.json', 'w', encoding='utf-8') as f:
        json.dump({
            'count': count,
            'results': results
        }, f, indent=2, ensure_ascii=False)
    print(f"  [PROGRESS SAVED] {count} tools processed")


def save_website_cache(cache: dict):
    """Save website cache."""
    with open('tool_websites.json', 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def save_final_results(results: list):
    """Save final results to CSV in database format."""

    if not results:
        print("No results to save")
        return

    # Remove internal status field
    clean_results = []
    for r in results:
        clean = {k: v for k, v in r.items() if k != '_status'}
        clean_results.append(clean)

    # Create DataFrame
    df = pd.DataFrame(clean_results)

    # Ensure exact column order from database
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

    # Add missing columns
    for col in database_columns:
        if col not in df.columns:
            df[col] = ""

    # Reorder to match database
    df = df[database_columns]

    # Save timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save as CSV
    csv_file = f"collected_data_{timestamp}.csv"
    df.to_csv(csv_file, index=False, encoding='utf-8')

    print(f"\n[SAVED] {csv_file}")
    print(f"Total records: {len(df)}")

    # Also save full data with status
    json_file = f"collected_data_{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"[SAVED] {json_file}")

    # Stats
    status_counts = {}
    for r in results:
        status = r.get('_status', 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1

    print(f"\nStatus breakdown:")
    for status, count in status_counts.items():
        print(f"  {status}: {count}")

    return csv_file


def main():
    """Main execution."""

    print("="*80)
    print("FULL DATA COLLECTION - Priority 1 Tools")
    print("="*80)

    # Load tools
    tools = load_priority_1_tools()
    print(f"\nLoaded {len(tools)} Priority 1 tools")

    # Check for resume
    resume_from = 0
    if os.path.exists('collection_progress.json'):
        with open('collection_progress.json', 'r', encoding='utf-8') as f:
            progress = json.load(f)
            resume_from = progress['count']

        resume = input(f"\nFound progress at {resume_from} tools. Resume? (y/n): ").strip().lower()
        if resume == 'y':
            print(f"Resuming from tool #{resume_from}")
        else:
            resume_from = 0

    # Ask for batch size
    print(f"\nHow many tools to process?")
    print(f"1. All {len(tools) - resume_from} remaining tools")
    print(f"2. Next 20 tools (test batch)")
    print(f"3. Next 50 tools")
    print(f"4. Custom number")

    choice = input("\nChoice (1-4): ").strip()

    batch_size = None
    if choice == "2":
        batch_size = 20
    elif choice == "3":
        batch_size = 50
    elif choice == "4":
        batch_size = int(input("Enter number: "))

    # Ask about auto-finding websites
    auto = input("\nAutomatically search for websites? (y/n): ").strip().lower()
    auto_find = auto == 'y'

    if not auto_find:
        print("\n*** Only processing tools with cached websites ***")

    # Estimate
    if batch_size:
        est_tools = min(batch_size, len(tools) - resume_from)
    else:
        est_tools = len(tools) - resume_from

    est_cost = est_tools * 0.002 * 0.6  # Assume 60% success rate
    est_time = est_tools * 10 / 60  # ~10 seconds per tool in minutes

    print(f"\nEstimates:")
    print(f"  Tools to process: ~{est_tools}")
    print(f"  Expected successful: ~{int(est_tools * 0.6)}")
    print(f"  Estimated cost: ${est_cost:.2f} USD")
    print(f"  Estimated time: {est_time:.1f} minutes")

    confirm = input("\nProceed? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled")
        return

    # Process tools
    print(f"\n{'='*80}")
    print("STARTING COLLECTION")
    print(f"{'='*80}")

    results = process_all_tools(
        tools,
        start_index=resume_from,
        batch_size=batch_size,
        auto_find_websites=auto_find
    )

    # Save results
    csv_file = save_final_results(results)

    print(f"\n{'='*80}")
    print("COLLECTION COMPLETE!")
    print(f"{'='*80}")
    print(f"\nOutput file: {csv_file}")
    print(f"\nNext steps:")
    print(f"1. Review {csv_file}")
    print(f"2. Check for data quality issues")
    print(f"3. Manually verify security certifications")
    print(f"4. Merge with merged_pref_top50.csv:")
    print(f"   import pandas as pd")
    print(f"   existing = pd.read_csv('merged_pref_top50.csv')")
    print(f"   new = pd.read_csv('{csv_file}')")
    print(f"   # Remove failed entries")
    print(f"   new_success = new[new['Product Description'].notna()]")
    print(f"   # Merge")
    print(f"   combined = pd.concat([existing, new_success], ignore_index=True)")
    print(f"   combined.to_csv('merged_pref_top50_updated.csv', index=False)")


if __name__ == "__main__":
    # Check requirements
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not found in .env")
        exit(1)

    if not os.path.exists('tools_priority_1_easy.txt'):
        print("ERROR: tools_priority_1_easy.txt not found")
        print("Run: python prioritize_tools.py first")
        exit(1)

    main()
