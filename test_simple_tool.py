"""
Test the pipeline on a simple, easy tool from Priority 1 list.
"""

import os
from dotenv import load_dotenv
from extract_tool_data import scrape_website, extract_with_ai, format_for_database
import json

load_dotenv()

# Test on a simple tool - let's use a real Priority 1 tool with a likely website
# We'll try a few common patterns

test_tools = [
    # Format: (tool_name, likely_website)
    ("Box", "https://www.box.com"),  # Well-known cloud storage
    ("Smokeball", "https://www.smokeball.com"),  # Legal practice management
    ("Junior", "https://www.junior.ai"),  # Might be junior.ai
]

print("="*80)
print("Testing Pipeline on Simple Tools")
print("="*80)

for tool_name, test_url in test_tools:
    print(f"\n{'='*80}")
    print(f"Testing: {tool_name}")
    print(f"URL: {test_url}")
    print(f"{'='*80}")

    # Try to scrape
    print("\n1. Scraping website...")
    content, success = scrape_website(test_url)

    if not success or not content:
        print(f"  X Failed to scrape {test_url}")
        print(f"  (Website may not exist or blocks automated access)")
        continue

    print(f"  [OK] Scraped {len(content)} characters")

    # Extract with AI
    print("\n2. Extracting with AI...")
    extracted = extract_with_ai(tool_name, test_url, content)

    if not extracted:
        print("  [ERROR] Failed to extract")
        continue

    print("  [OK] Extracted successfully!")

    # Format
    formatted = format_for_database(extracted, tool_name, test_url)

    # Show key fields
    print("\n3. Key extracted fields:")
    key_fields = [
        "Vendor Name",
        "Product Name",
        "Product Description",
        "Legal Functionality",
        "AI Powered",
        "Deployment Model",
    ]

    for field in key_fields:
        value = formatted.get(field, "")
        if value:
            display = value[:80] + "..." if len(value) > 80 else value
            print(f"   {field:25s}: {display}")
        else:
            print(f"   {field:25s}: [EMPTY]")

    # Check for certifications
    iso = formatted.get("ISO Certifications", "")
    sec = formatted.get("Security & Compliance Certifications", "")

    if iso or sec:
        print("\n   WARNING - Certifications found (verify manually):")
        if iso:
            print(f"   ISO: {iso}")
        if sec:
            print(f"   Security: {sec}")

    # Save this one
    output_file = f"test_result_{tool_name.lower().replace(' ', '_')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(formatted, f, indent=2, ensure_ascii=False)

    print(f"\n   Saved to: {output_file}")

    # Only test one successful extraction
    print(f"\n{'='*80}")
    print("Test complete! Review the output above.")
    print(f"{'='*80}")
    break

print("\n\nNext steps:")
print("1. Review the extracted data above")
print("2. Visit the website manually to verify accuracy")
print("3. Check if Legal Functionality category is correct")
print("4. Verify any security certifications mentioned")
print("\nIf quality looks good, proceed to batch processing!")
