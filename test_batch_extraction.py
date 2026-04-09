"""
Test batch extraction on 5-10 tools to review data quality.
Shows complete extracted data for each tool.
"""

import os
from dotenv import load_dotenv
from extract_tool_data import scrape_website, extract_with_ai, format_for_database
import json
import pandas as pd
from datetime import datetime

load_dotenv()

# Test tools - mix of known websites and ones we'll search for
test_tools = [
    # (tool_name, website_url or None)
    ("Smokeball", "https://www.smokeball.com"),
    ("Junior", "https://www.junior.ai"),
    ("CaseBlink", "https://www.caseblink.com"),
    ("Rocket Matter", "https://www.rocketmatter.com"),
    ("PracticePanther", "https://www.practicepanther.com"),
]

def print_extraction_summary(tool_name: str, formatted: dict):
    """Print a nice summary of extracted data."""

    print("\n" + "="*80)
    print(f"EXTRACTED DATA: {tool_name}")
    print("="*80)

    # Core fields
    print("\n--- CORE INFORMATION ---")
    core_fields = [
        "Vendor Name",
        "Product Name",
        "Vendor Overview",
        "Product Description"
    ]
    for field in core_fields:
        value = formatted.get(field, "")
        if value:
            # Wrap long text
            if len(value) > 70:
                print(f"{field}:")
                print(f"  {value[:200]}...")
            else:
                print(f"{field}: {value}")
        else:
            print(f"{field}: [EMPTY]")

    # Categorization
    print("\n--- CATEGORIZATION ---")
    cat_fields = [
        "Legal Functionality",
        "Functionality Sub-Category",
        "Main problem solved",
        "Primary User Segment",
        "Maturity Entry Level"
    ]
    for field in cat_fields:
        value = formatted.get(field, "")
        if value:
            print(f"{field}: {value}")
        else:
            print(f"{field}: [EMPTY]")

    # Technical details
    print("\n--- TECHNICAL ---")
    tech_fields = [
        "AI Powered",
        "AI Platform Type",
        "Deployment Model",
        "Pricing Model",
        "Languages Supported"
    ]
    for field in tech_fields:
        value = formatted.get(field, "")
        if value:
            print(f"{field}: {value}")
        else:
            print(f"{field}: [EMPTY]")

    # Location & Compliance
    print("\n--- LOCATION & COMPLIANCE ---")
    loc_fields = [
        "HQ",
        "Regions Served",
        "ISO Certifications",
        "Security & Compliance Certifications"
    ]
    for field in loc_fields:
        value = formatted.get(field, "")
        if value:
            if "Certification" in field:
                print(f"{field}: {value} *** VERIFY MANUALLY ***")
            else:
                print(f"{field}: {value}")
        else:
            print(f"{field}: [EMPTY]")

    # Pricing
    print("\n--- PRICING & AVAILABILITY ---")
    price_fields = [
        "Approx. Price Range (AUD)",
        "Demo / Proof of Concept Available",
        "Ease of Purchase",
        "Adoption Level"
    ]
    for field in price_fields:
        value = formatted.get(field, "")
        if value:
            print(f"{field}: {value}")
        else:
            print(f"{field}: [EMPTY]")

    # Count filled fields
    filled = sum(1 for v in formatted.values() if v and str(v).strip())
    total = len(formatted)
    pct = (filled / total) * 100

    print("\n--- COMPLETENESS ---")
    print(f"Fields filled: {filled}/{total} ({pct:.1f}%)")

    # Warnings
    warnings = []

    if not formatted.get("Legal Functionality"):
        warnings.append("Missing Legal Functionality (CRITICAL)")

    if not formatted.get("Product Description"):
        warnings.append("Missing Product Description")

    if formatted.get("ISO Certifications") or formatted.get("Security & Compliance Certifications"):
        warnings.append("Has certifications - MUST VERIFY MANUALLY")

    if filled > 20:
        warnings.append("Suspiciously complete - check for AI hallucination")

    if warnings:
        print("\n*** WARNINGS ***")
        for w in warnings:
            print(f"  ! {w}")


def main():
    """Run batch test."""

    print("="*80)
    print("BATCH EXTRACTION TEST")
    print("="*80)
    print(f"\nTesting {len(test_tools)} tools")
    print("This will use OpenAI API (estimated cost: ~$0.01)")

    input("\nPress Enter to continue...")

    results = []

    for i, (tool_name, url) in enumerate(test_tools, 1):
        print(f"\n\n{'='*80}")
        print(f"[{i}/{len(test_tools)}] PROCESSING: {tool_name}")
        print(f"{'='*80}")
        print(f"URL: {url}")

        # Scrape
        print("\nStep 1: Scraping website...")
        content, success = scrape_website(url)

        if not success or not content:
            print(f"  [FAILED] Could not scrape {url}")
            results.append({
                "Tool": tool_name,
                "Status": "scrape_failed",
                "URL": url
            })
            continue

        print(f"  [OK] Scraped {len(content)} characters")

        # Extract
        print("\nStep 2: Extracting with AI...")
        extracted = extract_with_ai(tool_name, url, content)

        if not extracted:
            print("  [FAILED] AI extraction failed")
            results.append({
                "Tool": tool_name,
                "Status": "extraction_failed",
                "URL": url
            })
            continue

        print(f"  [OK] Extracted {len([v for v in extracted.values() if v])} fields")

        # Format
        print("\nStep 3: Formatting...")
        formatted = format_for_database(extracted, tool_name, url)

        # Show summary
        print_extraction_summary(tool_name, formatted)

        # Add to results
        formatted["_test_status"] = "success"
        results.append(formatted)

        # Save individual result
        filename = f"test_result_{tool_name.lower().replace(' ', '_')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(formatted, f, indent=2, ensure_ascii=False)

        print(f"\n[SAVED] {filename}")

    # Save all results as CSV
    print("\n\n" + "="*80)
    print("SAVING RESULTS")
    print("="*80)

    if results:
        df = pd.DataFrame(results)

        # Remove status column for CSV
        if '_test_status' in df.columns:
            df = df.drop('_test_status', axis=1)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file = f"test_batch_results_{timestamp}.csv"

        df.to_csv(csv_file, index=False, encoding='utf-8')

        print(f"\n[OK] Saved to {csv_file}")
        print(f"[OK] Processed {len(results)} tools")

        # Summary stats
        success_count = sum(1 for r in results if r.get('_test_status') == 'success')
        print(f"\nSuccess rate: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print("\nNext steps:")
    print("1. Review the extracted data above")
    print("2. Check CSV file for side-by-side comparison")
    print("3. Manually verify a few websites to check accuracy")
    print("4. Pay special attention to:")
    print("   - Legal Functionality categorization")
    print("   - Security certifications (verify these manually)")
    print("   - Completeness (too complete might mean hallucination)")
    print("\nIf quality looks good, proceed to batch processing!")


if __name__ == "__main__":
    # Check if we have API key
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not found in .env file")
        exit(1)

    main()
