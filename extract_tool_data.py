"""
Stage 2: Extract structured data from tool websites.

This script:
1. Loads tool websites from tool_websites.json
2. Scrapes each website
3. Extracts structured data using AI
4. Saves results to CSV for review

CONSERVATIVE APPROACH:
- Only include data explicitly stated on website
- Skip uncertain fields (security certs unless clearly stated)
- Mark fields with confidence levels
"""

import os
import json
import time
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional
import re
from datetime import datetime

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def scrape_website(url: str, max_chars: int = 40000) -> tuple[str, bool]:
    """
    Scrape website content.

    Returns:
        (content, success)
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        print(f"  Fetching {url}...")
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'iframe', 'noscript']):
            element.decompose()

        # Get text
        text = soup.get_text(separator=' ', strip=True)

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        # Also try to get meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            text = f"META DESCRIPTION: {meta_desc['content']} | CONTENT: {text}"

        print(f"  [OK] Extracted {len(text)} characters")
        return text[:max_chars], True

    except Exception as e:
        print(f"  [ERROR] {e}")
        return "", False


def extract_with_ai(tool_name: str, website_url: str, content: str) -> Dict:
    """Extract structured data using OpenAI API."""

    system_prompt = """You are a legal technology data extraction specialist. Extract structured information from the website content provided.

CRITICAL EXTRACTION RULES:
1. ONLY extract information EXPLICITLY stated on the website
2. For certifications (ISO 27001, SOC 2, GDPR), ONLY include if clearly mentioned on the page
3. For security/compliance, be VERY conservative - only include if specifically listed
4. If information is unclear or not found, return empty string ""
5. Do NOT infer, assume, or guess
6. Better to leave a field empty than to include uncertain data

Field Guidelines:
- Legal Functionality: Choose ONE: "Contracting & Document Automation", "Matter, Workflow & Intake Management", "Litigation, Disputes & Investigations", "Legal Operations & Analytics", "Compliance, Risk & Governance", "AI Legal Assistants & Productivity Tools", "Knowledge, Search & Precedent Management", "Intellectual Property, Technology & Data", "Legal Research & Knowledge"
- AI Powered: "Yes" only if AI/ML/LLM is explicitly mentioned. "No" otherwise.
- Pricing Model: "Subscription (SaaS)", "Tiered / Plan-Based", "Usage-Based / Consumption", "One-time License", "Custom Pricing"
- Deployment Model: "Cloud (SaaS)", "On-Premise", "Hybrid"
- Maturity Entry Level: "Quick Win", "Advanced", "Enterprise-grade", or "Experimental / early stage"
- Primary User Segment: e.g., "Corporate legal", "Private practice", "Legal Operations Professionals", "Contract Management Teams / Procurement"

Return a JSON object with these fields. Use "" for unknown values."""

    user_prompt = f"""Tool/Vendor Name: {tool_name}
Website URL: {website_url}

Website Content:
{content[:25000]}

Extract all available information as JSON with these fields:
- Vendor Name
- Vendor Overview (1-2 sentences)
- Product Name
- Product Description (2-3 sentences)
- Legal Functionality
- Main problem solved
- Primary User Segment
- Maturity Entry Level
- Regions Served
- AI Powered (Yes/No)
- AI Platform Type (if AI-powered)
- Pricing Model
- Demo / Proof of Concept Available
- Deployment Model
- Languages Supported
- HQ (headquarters city/country)
- ISO Certifications (ONLY if explicitly stated)
- Security & Compliance Certifications (ONLY if explicitly stated: SOC 2, GDPR, etc.)
- Approx. Price Range (AUD): "<$10K", "$10K–$50K", "$51K-$100K", "$101K+" (only if pricing visible)
"""

    try:
        print("  Extracting data with AI...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.05,  # Very low for factual extraction
            max_tokens=2000
        )

        data = json.loads(response.choices[0].message.content)
        print(f"  [OK] Extracted {len([v for v in data.values() if v])} fields")
        return data

    except Exception as e:
        print(f"  [ERROR] AI extraction error: {e}")
        return {}


def format_for_database(data: Dict, tool_name: str, website_url: str) -> Dict:
    """Format extracted data to match database schema."""

    # All database fields
    fields = [
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

    formatted = {}

    for field in fields:
        if field == "Vendor Name":
            formatted[field] = data.get(field, tool_name)
        elif field == "Vendor Website":
            formatted[field] = website_url
        elif field in ["Customer Reviews", "Customer Feedback Rating", "Vendor Contact Details"]:
            # Always skip these fields
            formatted[field] = ""
        elif field in data:
            value = data[field]
            # Normalize None, null, N/A
            if value in [None, "null", "N/A", "n/a", "None", "unknown", "Unknown"]:
                formatted[field] = ""
            else:
                formatted[field] = str(value).strip()
        else:
            formatted[field] = ""

    # Normalize AI Powered
    ai_val = formatted.get("AI Powered", "").lower()
    if ai_val in ["yes", "true", "1"]:
        formatted["AI Powered"] = "Yes"
    elif ai_val in ["no", "false", "0"]:
        formatted["AI Powered"] = "No"
    else:
        formatted["AI Powered"] = ""

    return formatted


def process_tools(tool_websites: Dict, batch_size: int = 10, start_index: int = 0) -> list:
    """
    Process multiple tools and extract data.

    Args:
        tool_websites: Dict mapping tool name to website URL
        batch_size: Number of tools to process
        start_index: Starting index (for resuming)

    Returns:
        List of extracted data dictionaries
    """
    results = []
    tools_list = list(tool_websites.items())[start_index:start_index + batch_size]

    print(f"\nProcessing {len(tools_list)} tools (starting from index {start_index})...")

    for i, (tool_name, url) in enumerate(tools_list, 1):
        print(f"\n{'='*80}")
        print(f"[{start_index + i}/{start_index + len(tools_list)}] {tool_name}")
        print(f"{'='*80}")

        # Scrape website
        content, success = scrape_website(url)

        if not success or not content:
            print(f"  ⚠️  Failed to scrape - skipping")
            # Still add entry with just name and URL
            results.append({
                "Vendor Name": tool_name,
                "Vendor Website": url,
                "_status": "scrape_failed"
            })
            continue

        # Extract data with AI
        extracted = extract_with_ai(tool_name, url, content)

        if not extracted:
            print(f"  ⚠️  Failed to extract data - skipping")
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

        print(f"  ✓ Complete!")

        # Rate limiting - be respectful
        if i < len(tools_list):
            time.sleep(2)

    return results


def main():
    """Main execution."""
    print("="*80)
    print("Legal Tech Data Extraction Pipeline - Stage 2")
    print("="*80)

    # Load tool websites
    try:
        with open('tool_websites.json', 'r', encoding='utf-8') as f:
            tool_websites = json.load(f)
        print(f"\nLoaded {len(tool_websites)} tool websites")
    except FileNotFoundError:
        print("\n❌ Error: tool_websites.json not found!")
        print("Run find_websites_auto.py first to collect website URLs")
        return

    # Ask user how many to process
    print("\nHow many tools to process?")
    print(f"Total available: {len(tool_websites)}")

    batch_size = input("\nEnter number (or 'all'): ").strip()

    if batch_size.lower() == 'all':
        batch_size = len(tool_websites)
    else:
        batch_size = int(batch_size)

    start_index = 0
    resume_file = 'extracted_data_partial.json'

    # Check for partial results
    if os.path.exists(resume_file):
        resume = input(f"\nFound partial results in {resume_file}. Resume? (y/n): ").strip().lower()
        if resume == 'y':
            with open(resume_file, 'r', encoding='utf-8') as f:
                partial = json.load(f)
            start_index = len(partial['results'])
            print(f"Resuming from index {start_index}")

    # Process tools
    print(f"\n{'='*80}")
    print(f"Starting extraction...")
    print(f"{'='*80}")

    results = process_tools(tool_websites, batch_size=batch_size, start_index=start_index)

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save as JSON (for review)
    json_file = f'extracted_data_{timestamp}.json'
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Saved JSON to: {json_file}")

    # Save as CSV (for database import)
    if results:
        df = pd.DataFrame(results)

        # Remove internal status column from CSV
        if '_status' in df.columns:
            status_counts = df['_status'].value_counts()
            print(f"\nExtraction Results:")
            for status, count in status_counts.items():
                print(f"  {status}: {count}")

            df = df.drop('_status', axis=1)

        csv_file = f'extracted_data_{timestamp}.csv'
        df.to_csv(csv_file, index=False, encoding='utf-8')

        print(f"✓ Saved CSV to: {csv_file}")

        # Summary
        print(f"\n{'='*80}")
        print(f"Extraction Complete!")
        print(f"{'='*80}")
        print(f"Processed: {len(results)} tools")
        print(f"\nNext steps:")
        print(f"1. Review {csv_file} for accuracy")
        print(f"2. Check for missing/incorrect data")
        print(f"3. Verify security certifications are correct")
        print(f"4. Merge with existing database")


if __name__ == "__main__":
    main()
