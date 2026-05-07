"""
Fastest way to add websites: paste a list of URLs and it will auto-match them.

Create a text file like this (bulk_urls.txt):

smokeball.com
caseblink.com
clio.com
mycase.com
practicepanther.com

Or with full URLs:
https://www.smokeball.com
https://www.caseblink.com

Then run this script to automatically match URLs to tool names.
"""

import json
import re


def normalize_name(name: str) -> str:
    """Normalize name for matching."""
    name = name.lower()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', '', name)
    return name


def extract_domain_keywords(url: str) -> set:
    """Extract keywords from domain for matching."""
    # Remove protocol and www
    domain = url.replace('https://', '').replace('http://', '')
    domain = domain.replace('www.', '')
    # Get just domain name (before first /)
    domain = domain.split('/')[0]
    # Remove TLD
    domain = re.sub(r'\.(com|ai|io|co|org|net).*$', '', domain)

    # Split on hyphens and dots
    parts = re.split(r'[-.]', domain)

    return set(p.lower() for p in parts if len(p) > 2)


def match_url_to_tool(url: str, tools: list) -> str:
    """Try to match a URL to a tool name."""

    url_keywords = extract_domain_keywords(url)

    # Try direct matches first
    for tool in tools:
        tool_norm = normalize_name(tool)

        # Check if URL domain contains tool name
        if tool_norm in url.lower():
            return tool

        # Check if tool name is in domain keywords
        if tool_norm in url_keywords:
            return tool

        # Check if any URL keyword is in tool name
        for keyword in url_keywords:
            if keyword in tool_norm and len(keyword) > 3:
                return tool

    return None


def main():
    """Main execution."""

    print("="*80)
    print("BULK WEBSITE INPUT")
    print("="*80)

    # Load tools
    tools = []
    with open('tools_priority_1_easy.txt', 'r', encoding='utf-8') as f:
        for line in f:
            match = re.match(r'^\d+\.\s+(.+)$', line.strip())
            if match:
                tools.append(match.group(1))

    print(f"\nLoaded {len(tools)} Priority 1 tools")

    # Load existing cache
    website_cache = {}
    try:
        with open('tool_websites.json', 'r', encoding='utf-8') as f:
            website_cache = json.load(f)
        print(f"Loaded {len(website_cache)} existing websites")
    except FileNotFoundError:
        print("No existing cache")

    # Check for bulk input file
    try:
        with open('bulk_urls.txt', 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
        print(f"\n[OK] Found bulk_urls.txt with {len(urls)} URLs")
    except FileNotFoundError:
        print("\n[INFO] No bulk_urls.txt found")
        print("\nCreate a file called 'bulk_urls.txt' with one URL per line:")
        print("  smokeball.com")
        print("  caseblink.com")
        print("  clio.com")
        print("\nOr with full URLs:")
        print("  https://www.smokeball.com")
        print("  https://www.caseblink.com")
        print("\nThen run this script again.")
        return

    # Process URLs
    print("\nMatching URLs to tools...")
    print("="*80)

    matched = 0
    unmatched_urls = []

    for url in urls:
        # Normalize URL
        if not url.startswith('http'):
            url = 'https://' + url
        if not url.startswith('https://www.') and not url.startswith('https://app.'):
            url = url.replace('https://', 'https://www.')

        # Try to match
        matched_tool = match_url_to_tool(url, tools)

        if matched_tool:
            website_cache[matched_tool] = url
            print(f"[OK] {matched_tool:40s} -> {url}")
            matched += 1
        else:
            unmatched_urls.append(url)
            print(f"[??] Could not match: {url}")

    # Save
    with open('tool_websites.json', 'w', encoding='utf-8') as f:
        json.dump(website_cache, f, indent=2, ensure_ascii=False)

    print()
    print("="*80)
    print("COMPLETE")
    print("="*80)
    print(f"Matched: {matched} URLs")
    print(f"Unmatched: {len(unmatched_urls)} URLs")
    print(f"Total in cache: {len(website_cache)} websites")

    if unmatched_urls:
        print("\nUnmatched URLs (you can manually add these to tool_websites.json):")
        for url in unmatched_urls:
            print(f"  {url}")

    print(f"\nSaved to: tool_websites.json")
    print("\nNext step:")
    print("  python run_quick_collection.py")


if __name__ == "__main__":
    main()
