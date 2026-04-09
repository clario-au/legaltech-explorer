"""
Quick test of the data collection pipeline on a single tool.

This helps verify the pipeline is working before processing all 369 tools.
"""

import os
from dotenv import load_dotenv
from extract_tool_data import scrape_website, extract_with_ai, format_for_database
import json

load_dotenv()


def test_single_tool(tool_name: str, website_url: str):
    """Test the pipeline on a single tool."""

    print("="*80)
    print(f"TESTING PIPELINE ON: {tool_name}")
    print("="*80)

    # Step 1: Scrape website
    print("\n1. Scraping website...")
    print(f"   URL: {website_url}")

    content, success = scrape_website(website_url)

    if not success:
        print("   ✗ Failed to scrape website")
        return

    print(f"   ✓ Scraped {len(content)} characters")
    print(f"\nFirst 500 chars:\n{content[:500]}...")

    # Step 2: Extract with AI
    print("\n2. Extracting data with AI...")

    extracted = extract_with_ai(tool_name, website_url, content)

    if not extracted:
        print("   ✗ Failed to extract data")
        return

    print("   ✓ Extraction successful!")
    print("\nExtracted data:")
    print(json.dumps(extracted, indent=2))

    # Step 3: Format for database
    print("\n3. Formatting for database...")

    formatted = format_for_database(extracted, tool_name, website_url)

    print("   ✓ Formatted successfully!")

    # Show non-empty fields
    print("\nNon-empty fields:")
    for key, value in formatted.items():
        if value and value.strip():
            print(f"   {key}: {value[:100]}...")

    # Show empty fields that should ideally be filled
    important_empty = []
    important_fields = [
        "Vendor Overview", "Product Description", "Legal Functionality",
        "AI Powered", "Deployment Model", "Pricing Model"
    ]

    for field in important_fields:
        if not formatted.get(field, "").strip():
            important_empty.append(field)

    if important_empty:
        print("\n⚠️  Important empty fields:")
        for field in important_empty:
            print(f"   - {field}")

    # Check for security certifications
    certs = formatted.get("ISO Certifications", "")
    security = formatted.get("Security & Compliance Certifications", "")

    if certs or security:
        print("\n⚠️  VERIFY THESE CERTIFICATIONS ON WEBSITE:")
        if certs:
            print(f"   ISO: {certs}")
        if security:
            print(f"   Security: {security}")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)

    return formatted


if __name__ == "__main__":
    print("Data Collection Pipeline - Single Tool Test\n")

    # Example tools from the database for testing
    examples = {
        "1": ("Agiloft", "https://www.agiloft.com"),
        "2": ("Ironclad", "https://www.ironcladapp.com"),
        "3": ("DocuSign", "https://www.docusign.com"),
    }

    print("Test with example tool or custom:")
    for key, (name, url) in examples.items():
        print(f"{key}. {name} ({url})")
    print("4. Custom tool")

    choice = input("\nChoice (1-4): ").strip()

    if choice in examples:
        tool_name, url = examples[choice]
    elif choice == "4":
        tool_name = input("Tool name: ").strip()
        url = input("Website URL: ").strip()
        if not url.startswith('http'):
            url = 'https://' + url
    else:
        print("Invalid choice")
        exit()

    # Run test
    result = test_single_tool(tool_name, url)

    if result:
        # Ask if user wants to save
        save = input("\nSave result to test_output.json? (y/n): ").strip().lower()

        if save == 'y':
            with open('test_output.json', 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print("✓ Saved to test_output.json")

        print("\nNext steps:")
        print("1. Review the extracted data above")
        print("2. Check the website manually to verify accuracy")
        print("3. If quality looks good, proceed with batch processing")
        print("4. If quality is poor, adjust prompts in extract_tool_data.py")
