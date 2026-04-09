"""
Data collection pipeline for missing legal tech tools.

Stage 1: Find vendor websites (using web search, NOT Legal Tech Hub)
Stage 2: Scrape website content
Stage 3: Extract structured data using AI API
Stage 4: Validate and format data for database

IMPORTANT:
- Avoid Legal Tech Hub as a data source
- Be conservative with security/compliance certifications (only include if explicitly stated)
- Skip fields that are uncertain (Customer Reviews, Contact Details)
- Focus on verifiable factual data
"""

import os
import json
import time
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv
import requests
from typing import Dict, List, Optional
import re

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Fields from the database schema
DATABASE_FIELDS = [
    "Vendor Name", "Vendor Overview", "Product Name", "Product Description",
    "Legal Functionality", "Functionality Sub-Category", "Main problem solved",
    "Primary User Segment", "Maturity Entry Level", "Regions Served",
    "AI Powered", "AI Platform Type", "Hosting Location", "Pricing Model",
    "Demo / Proof of Concept Available", "Adoption Level", "Ease of Purchase",
    "Deployment Model", "Industry Focus", "Languages Supported", "HQ",
    "Office Locations", "Hosting Provider", "ISO Certifications",
    "Security & Compliance Certifications", "Approx. Price Range (AUD)",
    "Customer Reviews", "Customer Feedback Rating", "Vendor Website",
    "Vendor Contact Details"
]

# Fields to SKIP (unreliable or hard to verify)
SKIP_FIELDS = [
    "Customer Reviews",
    "Customer Feedback Rating",
    "Vendor Contact Details",  # Hard to extract accurately
]

# Fields requiring HIGH confidence (only populate if explicitly stated)
HIGH_CONFIDENCE_FIELDS = [
    "ISO Certifications",
    "Security & Compliance Certifications",
    "SOC 2 (Type I or II)",
    "GDPR Compliance (EU)",
    "Hosting Provider",
    "Hosting Location"
]

def find_vendor_website(vendor_name: str, use_search_api: bool = False) -> Optional[str]:
    """
    Find the vendor's official website using web search.

    Args:
        vendor_name: Name of the vendor/tool
        use_search_api: If True, use a search API (requires setup). Otherwise, manual entry.

    Returns:
        Website URL or None if not found
    """
    # For now, this will need manual entry or a search API integration
    # You could integrate with Google Custom Search API, Bing Search API, etc.

    print(f"\n{'='*80}")
    print(f"Finding website for: {vendor_name}")
    print(f"{'='*80}")

    # TODO: Integrate with search API
    # For now, return None to indicate manual entry needed
    return None


def scrape_website_content(url: str, max_chars: int = 50000) -> str:
    """
    Fetch and extract text content from a website.

    Args:
        url: Website URL
        max_chars: Maximum characters to extract

    Returns:
        Extracted text content
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        # Simple text extraction (you may want to use BeautifulSoup for better extraction)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer"]):
            script.decompose()

        # Get text
        text = soup.get_text(separator=' ', strip=True)

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text[:max_chars]

    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return ""


def extract_data_with_ai(vendor_name: str, website_content: str) -> Dict:
    """
    Extract structured data from website content using OpenAI API.

    Args:
        vendor_name: Name of the vendor
        website_content: Text content from website

    Returns:
        Dictionary with extracted data
    """

    system_prompt = f"""You are a legal tech data extraction specialist. Extract structured information about the legal tech tool/vendor from the provided website content.

CRITICAL RULES:
1. ONLY include information that is EXPLICITLY stated on the website
2. For security certifications (ISO, SOC 2, GDPR), ONLY include if clearly mentioned
3. If information is not found or unclear, use empty string "" or null
4. Be conservative - it's better to leave fields empty than to guess
5. Do NOT infer or assume information

Extract the following fields (if available):
- Vendor Name: The company name
- Vendor Overview: Brief description of the company (1-2 sentences)
- Product Name: Main product/tool name
- Product Description: What the product does (2-3 sentences)
- Legal Functionality: Primary category (e.g., "Contracting & Document Automation", "Matter, Workflow & Intake Management", etc.)
- Main problem solved: What problem does it solve?
- Primary User Segment: Who uses it? (e.g., "Corporate legal", "Private practice", "Legal Operations Professionals")
- Maturity Entry Level: "Quick Win", "Advanced", "Enterprise-grade", or "Experimental / early stage"
- Regions Served: Geographic regions where available
- AI Powered: "Yes" or "No" - only Yes if AI/ML is explicitly mentioned
- AI Platform Type: If AI-powered, what type? (e.g., "Large Language Model (LLM) Platforms", "Natural Language Processing (NLP)")
- Pricing Model: "Subscription (SaaS)", "Tiered / Plan-Based", "Usage-Based / Consumption", "One-time License", etc.
- Demo / Proof of Concept Available: "Demo Available", "Free Trial", or ""
- Deployment Model: "Cloud (SaaS)", "On-Premise", "Hybrid", etc.
- Languages Supported: "English only" or list other languages
- HQ: Headquarters location (city, country)
- ISO Certifications: ONLY if explicitly mentioned (e.g., "ISO 27001")
- Security & Compliance Certifications: ONLY if explicitly mentioned (e.g., "SOC 2 (Type I or II)", "GDPR Compliance (EU)")
- Approx. Price Range (AUD): "<$10K", "$10K–$50K", "$51K-$100K", or "$101K+" - only if pricing info available
- Vendor Website: The URL

Return ONLY a valid JSON object with these fields. Use empty string "" for unknown fields.
Do NOT include Customer Reviews, Customer Feedback Rating, or Vendor Contact Details."""

    user_prompt = f"""Vendor/Tool Name: {vendor_name}

Website Content:
{website_content[:30000]}

Extract all available information as JSON."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # More cost-effective for extraction
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1  # Low temperature for factual extraction
        )

        result = json.loads(response.choices[0].message.content)
        return result

    except Exception as e:
        print(f"Error extracting data with AI: {e}")
        return {}


def validate_and_format_data(data: Dict, vendor_name: str) -> Dict:
    """
    Validate extracted data and ensure it matches database schema.

    Args:
        data: Extracted data dictionary
        vendor_name: Original vendor name

    Returns:
        Validated and formatted data dictionary
    """
    formatted = {}

    # Ensure vendor name is present
    formatted["Vendor Name"] = data.get("Vendor Name", vendor_name)

    # Copy other fields
    for field in DATABASE_FIELDS:
        if field in SKIP_FIELDS:
            formatted[field] = ""
        elif field in data:
            value = data[field]
            # Normalize empty values
            if value in [None, "null", "N/A", "n/a"]:
                formatted[field] = ""
            else:
                formatted[field] = str(value).strip()
        else:
            formatted[field] = ""

    # Validate AI Powered field
    if formatted.get("AI Powered", "").lower() in ["yes", "true", "1"]:
        formatted["AI Powered"] = "Yes"
    elif formatted.get("AI Powered", "").lower() in ["no", "false", "0"]:
        formatted["AI Powered"] = "No"
    else:
        formatted["AI Powered"] = ""

    return formatted


def process_single_tool(vendor_name: str, website_url: Optional[str] = None) -> Optional[Dict]:
    """
    Process a single tool through the entire pipeline.

    Args:
        vendor_name: Name of the vendor/tool
        website_url: Optional website URL (if None, will try to find it)

    Returns:
        Extracted data dictionary or None if failed
    """
    print(f"\n{'='*80}")
    print(f"Processing: {vendor_name}")
    print(f"{'='*80}")

    # Step 1: Find website if not provided
    if not website_url:
        website_url = find_vendor_website(vendor_name)
        if not website_url:
            print(f"⚠️  No website found for {vendor_name}. Please provide manually.")
            return None

    print(f"Website: {website_url}")

    # Step 2: Scrape website content
    print("Scraping website content...")
    content = scrape_website_content(website_url)

    if not content:
        print(f"⚠️  Could not scrape content from {website_url}")
        return None

    print(f"Extracted {len(content)} characters of content")

    # Step 3: Extract data with AI
    print("Extracting structured data with AI...")
    extracted_data = extract_data_with_ai(vendor_name, content)

    if not extracted_data:
        print(f"⚠️  Could not extract data for {vendor_name}")
        return None

    # Step 4: Validate and format
    print("Validating and formatting data...")
    formatted_data = validate_and_format_data(extracted_data, vendor_name)
    formatted_data["Vendor Website"] = website_url

    print("✓ Successfully processed!")

    return formatted_data


def main():
    """Main execution function."""

    print("="*80)
    print("Legal Tech Tool Data Collection Pipeline")
    print("="*80)

    # Load missing tools list
    with open('tools_not_in_database.txt', 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Parse tool names (skip header lines)
    tool_names = []
    for line in lines:
        line = line.strip()
        # Match lines like "1. Tool Name"
        match = re.match(r'^\d+\.\s+(.+)$', line)
        if match:
            tool_names.append(match.group(1))

    print(f"\nFound {len(tool_names)} tools to process")

    # Ask user how many to process
    print("\nOptions:")
    print("1. Process all tools (may take hours)")
    print("2. Process first N tools")
    print("3. Process specific tool by name")

    choice = input("\nEnter choice (1/2/3): ").strip()

    tools_to_process = []

    if choice == "1":
        tools_to_process = tool_names
    elif choice == "2":
        n = int(input("How many tools to process? "))
        tools_to_process = tool_names[:n]
    elif choice == "3":
        name = input("Enter tool name: ").strip()
        tools_to_process = [name]
    else:
        print("Invalid choice")
        return

    print(f"\nWill process {len(tools_to_process)} tools")
    print("\nNOTE: You will need to provide website URLs manually for each tool.")
    print("This is Stage 1 - finding websites. Website scraping happens in Stage 2.")

    # Collect website URLs
    website_mapping = {}

    print("\n" + "="*80)
    print("STAGE 1: Collecting Website URLs")
    print("="*80)

    for i, tool_name in enumerate(tools_to_process, 1):
        print(f"\n[{i}/{len(tools_to_process)}] {tool_name}")
        url = input("Enter website URL (or press Enter to skip): ").strip()

        if url:
            if not url.startswith('http'):
                url = 'https://' + url
            website_mapping[tool_name] = url
        else:
            print(f"  Skipped {tool_name}")

    # Save website mapping
    with open('tool_websites.json', 'w', encoding='utf-8') as f:
        json.dump(website_mapping, f, indent=2)

    print(f"\n✓ Saved {len(website_mapping)} website URLs to tool_websites.json")
    print("\nTo continue with data extraction, run this script again and it will use the saved URLs.")


if __name__ == "__main__":
    # Check if BeautifulSoup is installed
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("⚠️  BeautifulSoup4 not installed. Installing...")
        import subprocess
        subprocess.check_call(["pip", "install", "beautifulsoup4"])

    main()
