"""
Update the embedded DATA array in index.html with the scored CSV.
"""

import pandas as pd
import json
import re

# Load the scored CSV
df = pd.read_csv('merged_pref_top50_updated.csv')

# Convert to JSON (list of dictionaries)
data_records = df.to_dict('records')

# Format as JavaScript array
js_data = "var DATA = " + json.dumps(data_records, indent=2, ensure_ascii=False) + ";"

# Read the HTML file
with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Find and replace the DATA array
# Pattern: var DATA = [...];
pattern = r'var DATA = \[.*?\];'

# Count how many matches we find
matches = re.findall(pattern, html, re.DOTALL)
print(f"Found {len(matches)} DATA array(s)")

if matches:
    # Replace the DATA array
    html_new = re.sub(pattern, js_data, html, count=1, flags=re.DOTALL)

    # Write back
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html_new)

    print(f"\n[OK] Updated index.html with {len(data_records)} tools")
    print(f"[OK] All tools now have popularity_score field")
else:
    print("\nERROR: Could not find DATA array in index.html")
    print("Looking for pattern: var DATA = [...]")
