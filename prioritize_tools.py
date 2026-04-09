"""
Prioritize and categorize tools by extraction difficulty.

Tools with "X by Y" pattern are often:
- Sub-products of larger platforms
- Hard to find standalone websites
- Limited public information

This script creates prioritized lists for data collection.
"""

import re
import json


def categorize_tool(tool_name: str) -> dict:
    """
    Categorize a tool by extraction difficulty.

    Returns:
        dict with 'category', 'priority', 'product_name', 'vendor_name'
    """

    # Pattern: "Product by Vendor"
    by_match = re.match(r'^(.+?)\s+by\s+(.+)$', tool_name, re.IGNORECASE)

    if by_match:
        product = by_match.group(1).strip()
        vendor = by_match.group(2).strip()

        # Check if vendor name appears again in product name (redundant)
        # e.g., "AI Billing Compliance by 273 Ventures AI Billing Compliance"
        if vendor.lower() in product.lower() or product.lower() in vendor.lower():
            return {
                'category': 'by_pattern_redundant',
                'priority': 4,  # Hardest - likely messy data
                'product_name': product,
                'vendor_name': vendor,
                'search_query': vendor  # Search for parent company
            }
        else:
            return {
                'category': 'by_pattern_clean',
                'priority': 3,  # Hard - sub-product
                'product_name': product,
                'vendor_name': vendor,
                'search_query': f"{product} {vendor}"  # Search for both
            }

    # Check for other difficult patterns

    # Pattern: Multiple words without clear structure (may be hard to search)
    word_count = len(tool_name.split())

    if word_count >= 6:
        return {
            'category': 'long_name',
            'priority': 2,  # Medium - might be descriptive or hard to search
            'product_name': tool_name,
            'vendor_name': None,
            'search_query': tool_name
        }

    # Simple, clean names (easiest)
    if word_count <= 3:
        return {
            'category': 'simple',
            'priority': 1,  # Easiest
            'product_name': tool_name,
            'vendor_name': None,
            'search_query': f"{tool_name} legal tech"
        }

    # Medium complexity
    return {
        'category': 'medium',
        'priority': 2,
        'product_name': tool_name,
        'vendor_name': None,
        'search_query': f"{tool_name} legal tech"
    }


def main():
    """Main execution."""

    print("="*80)
    print("Tool Prioritization for Data Collection")
    print("="*80)

    # Load tools
    with open('tools_not_in_database.txt', 'r', encoding='utf-8') as f:
        lines = f.readlines()

    tool_names = []
    for line in lines:
        match = re.match(r'^\d+\.\s+(.+)$', line.strip())
        if match:
            tool_names.append(match.group(1))

    print(f"\nTotal tools: {len(tool_names)}")

    # Categorize all tools
    categorized = []
    for tool in tool_names:
        cat = categorize_tool(tool)
        cat['original_name'] = tool
        categorized.append(cat)

    # Sort by priority (easiest first)
    categorized.sort(key=lambda x: (x['priority'], x['original_name']))

    # Statistics
    from collections import Counter
    category_counts = Counter(t['category'] for t in categorized)

    print("\nCategories:")
    for category, count in category_counts.most_common():
        pct = count / len(categorized) * 100
        print(f"  {category:25s}: {count:3d} ({pct:5.1f}%)")

    # Create priority lists
    priority_groups = {
        1: [t for t in categorized if t['priority'] == 1],
        2: [t for t in categorized if t['priority'] == 2],
        3: [t for t in categorized if t['priority'] == 3],
        4: [t for t in categorized if t['priority'] == 4],
    }

    print("\nPriority Groups:")
    print("  Priority 1 (Simple names - EASIEST):", len(priority_groups[1]))
    print("  Priority 2 (Medium complexity):", len(priority_groups[2]))
    print("  Priority 3 (Clean 'by' pattern):", len(priority_groups[3]))
    print("  Priority 4 (Redundant 'by' pattern - HARDEST):", len(priority_groups[4]))

    # Save prioritized lists

    # 1. Easy tools (Priority 1)
    easy_tools = [t['original_name'] for t in priority_groups[1]]
    with open('tools_priority_1_easy.txt', 'w', encoding='utf-8') as f:
        f.write(f"PRIORITY 1: Simple Tools (EASIEST - Start Here)\n")
        f.write(f"Total: {len(easy_tools)}\n")
        f.write("="*80 + "\n\n")
        for i, tool in enumerate(easy_tools, 1):
            f.write(f"{i}. {tool}\n")

    # 2. Medium tools (Priority 2)
    medium_tools = [t['original_name'] for t in priority_groups[2]]
    with open('tools_priority_2_medium.txt', 'w', encoding='utf-8') as f:
        f.write(f"PRIORITY 2: Medium Complexity Tools\n")
        f.write(f"Total: {len(medium_tools)}\n")
        f.write("="*80 + "\n\n")
        for i, tool in enumerate(medium_tools, 1):
            f.write(f"{i}. {tool}\n")

    # 3. Hard tools (Priority 3 + 4)
    hard_tools = [t['original_name'] for t in priority_groups[3] + priority_groups[4]]
    with open('tools_priority_3_hard.txt', 'w', encoding='utf-8') as f:
        f.write(f"PRIORITY 3: Hard Tools (Sub-products, 'by' pattern)\n")
        f.write(f"Total: {len(hard_tools)}\n")
        f.write("="*80 + "\n\n")
        for i, tool in enumerate(hard_tools, 1):
            cat_info = categorized[categorized.index([t for t in categorized if t['original_name'] == tool][0])]
            f.write(f"{i}. {tool}\n")
            if cat_info['vendor_name']:
                f.write(f"   Product: {cat_info['product_name']}\n")
                f.write(f"   Vendor: {cat_info['vendor_name']}\n")

    # Save full categorization as JSON
    with open('tools_categorized.json', 'w', encoding='utf-8') as f:
        json.dump(categorized, f, indent=2, ensure_ascii=False)

    print("\nFiles created:")
    print("  ✓ tools_priority_1_easy.txt - Start here ({} tools)".format(len(easy_tools)))
    print("  ✓ tools_priority_2_medium.txt - Do second ({} tools)".format(len(medium_tools)))
    print("  ✓ tools_priority_3_hard.txt - Do last ({} tools)".format(len(hard_tools)))
    print("  ✓ tools_categorized.json - Full categorization data")

    print("\n" + "="*80)
    print("RECOMMENDATION")
    print("="*80)
    print(f"\n1. START with Priority 1 tools ({len(easy_tools)} tools)")
    print("   - Simple names like 'Box', 'Finch', 'Junior'")
    print("   - Likely to have standalone websites")
    print("   - Higher success rate")
    print()
    print(f"2. THEN do Priority 2 tools ({len(medium_tools)} tools)")
    print("   - Medium complexity names")
    print("   - Should still be findable")
    print()
    print(f"3. SKIP or manually handle Priority 3 tools ({len(hard_tools)} tools)")
    print("   - Sub-products of larger platforms")
    print("   - May require searching parent company websites")
    print("   - Lower success rate with automated extraction")
    print()
    print("Expected success rates:")
    print("  Priority 1: ~80-90%")
    print("  Priority 2: ~60-70%")
    print("  Priority 3: ~30-40%")
    print()
    print("=" * 80)

    # Show some examples
    print("\nExamples of Priority 1 (Easy) tools:")
    for tool in easy_tools[:10]:
        print(f"  • {tool}")

    print(f"\n... and {len(easy_tools) - 10} more")

    print("\nExamples of Priority 3 (Hard) tools:")
    for tool in hard_tools[:10]:
        cat_info = [t for t in categorized if t['original_name'] == tool][0]
        print(f"  • {tool}")
        if cat_info['vendor_name']:
            print(f"    → Product: {cat_info['product_name']}")
            print(f"    → Vendor: {cat_info['vendor_name']}")


if __name__ == "__main__":
    main()
