"""
Automated website finder using web search.
This script helps find official websites for legal tech tools.

Uses DuckDuckGo search (no API key required) or manual Google search.
AVOIDS Legal Tech Hub results.
"""

import json
import time
import re
from typing import Optional, List
import requests
from bs4 import BeautifulSoup


def search_duckduckgo(query: str, max_results: int = 5) -> List[dict]:
    """
    Search DuckDuckGo for a query and return results.

    Args:
        query: Search query
        max_results: Maximum number of results to return

    Returns:
        List of result dictionaries with 'title' and 'url'
    """
    try:
        # DuckDuckGo HTML search
        url = "https://duckduckgo.com/html/"
        params = {'q': query}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.post(url, data=params, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        results = []

        # Find result links
        for result in soup.find_all('a', class_='result__a', limit=max_results):
            title = result.get_text(strip=True)
            link = result.get('href', '')

            # Skip Legal Tech Hub results
            if 'legaltechnologyhub' in link.lower():
                continue

            if link and title:
                results.append({
                    'title': title,
                    'url': link
                })

        return results

    except Exception as e:
        print(f"Error searching DuckDuckGo: {e}")
        return []


def find_likely_official_website(tool_name: str) -> Optional[str]:
    """
    Find the most likely official website for a tool.

    Args:
        tool_name: Name of the tool/vendor

    Returns:
        Most likely official website URL or None
    """
    print(f"\n{'='*80}")
    print(f"Searching for: {tool_name}")
    print(f"{'='*80}")

    # Clean up tool name for search
    # Remove "by [company]" patterns
    clean_name = re.sub(r'\s+by\s+.*$', '', tool_name, flags=re.IGNORECASE)

    # Search query
    query = f"{clean_name} legal tech official website"

    print(f"Search query: {query}")

    # Try DuckDuckGo search
    results = search_duckduckgo(query)

    if not results:
        print("No results found via automated search.")
        return None

    print(f"\nFound {len(results)} results:")
    for i, result in enumerate(results, 1):
        print(f"  {i}. {result['title']}")
        print(f"     {result['url']}")

    # Simple heuristic: prefer domains that contain the tool name
    tool_name_keywords = clean_name.lower().replace(' ', '').replace('-', '')

    best_match = None
    best_score = 0

    for result in results:
        url_lower = result['url'].lower()
        domain = re.search(r'https?://([^/]+)', url_lower)

        if domain:
            domain_str = domain.group(1).replace('www.', '')

            # Score based on tool name in domain
            score = 0

            # Check if tool name words are in domain
            name_words = clean_name.lower().split()
            for word in name_words:
                if len(word) > 2 and word in domain_str:
                    score += 10

            # Prefer .com, .ai, .io, .co domains
            if any(domain_str.endswith(ext) for ext in ['.com', '.ai', '.io', '.co']):
                score += 2

            # Penalize common platforms
            if any(platform in domain_str for platform in ['linkedin', 'facebook', 'twitter', 'youtube', 'crunchbase']):
                score -= 10

            if score > best_score:
                best_score = score
                best_match = result['url']

    if best_match:
        print(f"\n✓ Best match: {best_match}")
        return best_match
    else:
        print("\n⚠️  Could not determine best match automatically")
        return results[0]['url'] if results else None


def process_tools_batch(tool_names: List[str], auto_mode: bool = False) -> dict:
    """
    Process a batch of tools to find their websites.

    Args:
        tool_names: List of tool names
        auto_mode: If True, automatically select best match. If False, ask user.

    Returns:
        Dictionary mapping tool name to website URL
    """
    website_mapping = {}

    for i, tool_name in enumerate(tool_names, 1):
        print(f"\n{'='*80}")
        print(f"[{i}/{len(tool_names)}] Processing: {tool_name}")
        print(f"{'='*80}")

        # Try to find website automatically
        suggested_url = find_likely_official_website(tool_name)

        if auto_mode and suggested_url:
            # Automatic mode - use suggested URL
            website_mapping[tool_name] = suggested_url
            print(f"✓ Auto-selected: {suggested_url}")
        else:
            # Manual confirmation mode
            if suggested_url:
                print(f"\nSuggested website: {suggested_url}")
                confirm = input("Accept this URL? (y/n/enter URL manually): ").strip().lower()

                if confirm == 'y':
                    website_mapping[tool_name] = suggested_url
                elif confirm == 'n':
                    manual_url = input("Enter correct URL (or press Enter to skip): ").strip()
                    if manual_url:
                        if not manual_url.startswith('http'):
                            manual_url = 'https://' + manual_url
                        website_mapping[tool_name] = manual_url
                else:
                    # User entered a URL directly
                    if confirm and confirm != 'n':
                        url = confirm
                        if not url.startswith('http'):
                            url = 'https://' + url
                        website_mapping[tool_name] = url
            else:
                # No suggestion found
                manual_url = input("Enter URL manually (or press Enter to skip): ").strip()
                if manual_url:
                    if not manual_url.startswith('http'):
                        manual_url = 'https://' + manual_url
                    website_mapping[tool_name] = manual_url

        # Small delay to be respectful to search engines
        if i < len(tool_names):
            time.sleep(2)

    return website_mapping


def main():
    """Main execution function."""
    print("="*80)
    print("Automated Website Finder for Legal Tech Tools")
    print("="*80)

    # Load missing tools
    with open('tools_not_in_database.txt', 'r', encoding='utf-8') as f:
        lines = f.readlines()

    tool_names = []
    for line in lines:
        line = line.strip()
        match = re.match(r'^\d+\.\s+(.+)$', line)
        if match:
            tool_names.append(match.group(1))

    print(f"\nFound {len(tool_names)} tools")

    # Load existing website mapping if it exists
    existing_mapping = {}
    try:
        with open('tool_websites.json', 'r', encoding='utf-8') as f:
            existing_mapping = json.load(f)
        print(f"Loaded {len(existing_mapping)} existing website URLs")
    except FileNotFoundError:
        print("No existing website mapping found")

    # Ask user which tools to process
    print("\nOptions:")
    print("1. Process all missing tools")
    print("2. Process first N tools")
    print("3. Process tools without websites (from existing mapping)")

    choice = input("\nEnter choice (1/2/3): ").strip()

    tools_to_process = []

    if choice == "1":
        tools_to_process = tool_names
    elif choice == "2":
        n = int(input("How many tools to process? "))
        tools_to_process = tool_names[:n]
    elif choice == "3":
        tools_to_process = [t for t in tool_names if t not in existing_mapping]
        print(f"Found {len(tools_to_process)} tools without websites")
    else:
        print("Invalid choice")
        return

    # Ask for auto mode
    auto_mode = input("\nUse automatic mode (y/n)? ").strip().lower() == 'y'

    if auto_mode:
        print("\n⚠️  Automatic mode - will use best guess for each website")
        print("Review the results in tool_websites.json after completion!")
    else:
        print("\n✓ Manual confirmation mode - you'll review each suggestion")

    # Process tools
    print(f"\nProcessing {len(tools_to_process)} tools...")

    new_mappings = process_tools_batch(tools_to_process, auto_mode=auto_mode)

    # Merge with existing mappings
    all_mappings = {**existing_mapping, **new_mappings}

    # Save results
    with open('tool_websites.json', 'w', encoding='utf-8') as f:
        json.dump(all_mappings, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*80}")
    print(f"✓ Complete!")
    print(f"{'='*80}")
    print(f"Found websites for {len(new_mappings)} tools")
    print(f"Total websites in database: {len(all_mappings)}")
    print(f"Saved to: tool_websites.json")
    print(f"\nTools still missing websites: {len(tool_names) - len(all_mappings)}")


if __name__ == "__main__":
    # Check if BeautifulSoup is installed
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("Installing required packages...")
        import subprocess
        subprocess.check_call(["pip", "install", "beautifulsoup4", "requests"])

    main()
