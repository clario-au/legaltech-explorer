"""
Semi-automated website finder that makes manual collection much faster.

This tool:
1. Shows you each tool name
2. Suggests likely website URL patterns
3. You just press Enter to accept or type the correct URL
4. Saves progress as you go
"""

import json
import re
import webbrowser

def load_all_tools():
    """Load all priority tools (Priority 1, 2, and 3)."""
    tools = []

    # Load Priority 1 (easy names)
    try:
        with open('tools_priority_1_easy.txt', 'r', encoding='utf-8') as f:
            for line in f:
                match = re.match(r'^\d+\.\s+(.+)$', line.strip())
                if match:
                    tools.append(match.group(1))
    except FileNotFoundError:
        pass

    # Load Priority 2 (medium)
    try:
        with open('tools_priority_2_medium.txt', 'r', encoding='utf-8') as f:
            for line in f:
                match = re.match(r'^\d+\.\s+(.+)$', line.strip())
                if match:
                    tools.append(match.group(1))
    except FileNotFoundError:
        pass

    # Load Priority 3 (hard - "X by Y" format)
    try:
        with open('tools_priority_3_hard.txt', 'r', encoding='utf-8') as f:
            for line in f:
                match = re.match(r'^\d+\.\s+(.+)$', line.strip())
                if match:
                    tools.append(match.group(1))
    except FileNotFoundError:
        pass

    return tools


def suggest_url(tool_name: str) -> str:
    """Suggest likely URL based on tool name."""
    # Clean name
    clean = tool_name.lower()
    clean = re.sub(r'[^\w\s-]', '', clean)
    clean = re.sub(r'\s+', '', clean)

    # Common patterns
    suggestions = [
        f"https://www.{clean}.com",
        f"https://{clean}.com",
        f"https://www.{clean}.ai",
        f"https://{clean}.ai",
    ]

    return suggestions[0]


def main():
    """Main interactive loop."""

    print("="*80)
    print("ASSISTED WEBSITE FINDER")
    print("="*80)
    print()
    print("For each tool, I'll suggest a likely URL.")
    print("Press Enter to accept, or type the correct URL.")
    print("Type 'skip' to skip a tool.")
    print("Type 'open' to open Google search in browser.")
    print("Type 'quit' to finish and save.")
    print()

    # Load tools
    tools = load_all_tools()
    print(f"Loaded {len(tools)} tools (Priority 1, 2, and 3)")

    # Load existing cache
    website_cache = {}
    try:
        with open('tool_websites.json', 'r', encoding='utf-8') as f:
            website_cache = json.load(f)
        print(f"Loaded {len(website_cache)} existing websites")
    except FileNotFoundError:
        print("No existing cache found")

    # Filter to tools without websites
    tools_to_process = [t for t in tools if t not in website_cache]
    print(f"\nNeed to find {len(tools_to_process)} websites")
    print()

    start_index = 0
    if input("Start from beginning? (y/n): ").strip().lower() == 'n':
        start_index = int(input("Start from which number? "))
        tools_to_process = tools_to_process[start_index:]

    print(f"\nProcessing {len(tools_to_process)} tools...")
    print("="*80)

    added = 0

    for i, tool_name in enumerate(tools_to_process, start_index + 1):
        print(f"\n[{i}/{len(tools) - len(website_cache)}] {tool_name}")

        # Suggest URL
        suggested = suggest_url(tool_name)
        print(f"Suggested: {suggested}")

        # Get input
        user_input = input("URL (Enter=accept, 'skip', 'open', or type URL): ").strip()

        if user_input.lower() == 'quit':
            print("\nStopping and saving progress...")
            break

        elif user_input.lower() == 'skip':
            print("Skipped")
            continue

        elif user_input.lower() == 'open':
            # Open Google search
            search_query = f"{tool_name} legal tech official website"
            search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
            webbrowser.open(search_url)
            print("Opened Google search in browser")

            # Ask again
            user_input = input("Enter URL: ").strip()
            if not user_input or user_input.lower() == 'skip':
                continue

        elif user_input == '':
            user_input = suggested

        # Add http if missing
        if user_input and not user_input.startswith('http'):
            user_input = 'https://' + user_input

        # Save to cache
        website_cache[tool_name] = user_input
        added += 1

        print(f"[OK] Added: {user_input}")

        # Save progress every 5 tools
        if added % 5 == 0:
            with open('tool_websites.json', 'w', encoding='utf-8') as f:
                json.dump(website_cache, f, indent=2, ensure_ascii=False)
            print(f"  [PROGRESS SAVED - {len(website_cache)} total websites]")

    # Final save
    with open('tool_websites.json', 'w', encoding='utf-8') as f:
        json.dump(website_cache, f, indent=2, ensure_ascii=False)

    print()
    print("="*80)
    print("COMPLETE")
    print("="*80)
    print(f"Added: {added} websites")
    print(f"Total in cache: {len(website_cache)} websites")
    print(f"Saved to: tool_websites.json")
    print()
    print("Next step:")
    print("  python run_quick_collection.py")
    print("  (This will extract data from all websites in the cache)")


if __name__ == "__main__":
    main()
