"""
Complete pipeline: Extract new tools + Add popularity scores + Merge with database.
Runs all 3 steps automatically.
"""

import subprocess
import sys
import time
import glob
import pandas as pd
from datetime import datetime

print("="*80)
print("COMPLETE PIPELINE: EXTRACT + SCORE + MERGE")
print("="*80)

# Step 1: Extract data for new tools
print("\n" + "="*80)
print("STEP 1: EXTRACT DATA FOR NEW TOOLS")
print("="*80)

print("\nRunning incremental data collection...")
result = subprocess.run([sys.executable, "run_incremental_collection.py"],
                       capture_output=False, text=True)

if result.returncode != 0:
    print("\nERROR: Data extraction failed!")
    sys.exit(1)

print("\n[OK] Data extraction complete!")

# Find the latest incremental file
incremental_files = glob.glob('new_tools_incremental_*.csv')
# Filter out partial and scored files
incremental_files = [f for f in incremental_files if '_partial' not in f and '_scored' not in f]

if not incremental_files:
    print("\nERROR: No incremental extraction file found!")
    sys.exit(1)

latest_extraction = sorted(incremental_files)[-1]
print(f"Latest extraction: {latest_extraction}")

# Step 2: Add Google Trends popularity scores
print("\n" + "="*80)
print("STEP 2: ADD GOOGLE TRENDS POPULARITY SCORES")
print("="*80)

print("\nRunning popularity scoring...")
result = subprocess.run([sys.executable, "add_google_trends_incremental.py"],
                       capture_output=False, text=True)

if result.returncode != 0:
    print("\nWARNING: Popularity scoring had issues, continuing anyway...")

# Find the scored file
scored_files = glob.glob('new_tools_incremental_*_scored.csv')
if scored_files:
    latest_scored = sorted(scored_files)[-1]
    print(f"\n[OK] Popularity scoring complete!")
    print(f"Scored file: {latest_scored}")
    new_tools_file = latest_scored
else:
    print("\nWARNING: No scored file found, using unscored extraction")
    new_tools_file = latest_extraction

# Step 3: Merge with existing database
print("\n" + "="*80)
print("STEP 3: MERGE WITH EXISTING DATABASE")
print("="*80)

# Load existing database
try:
    df_existing = pd.read_csv('merged_pref_top50_updated.csv')
    print(f"\nLoaded existing database: {len(df_existing)} tools")
except FileNotFoundError:
    print("\nERROR: merged_pref_top50_updated.csv not found!")
    sys.exit(1)

# Load new tools
try:
    df_new = pd.read_csv(new_tools_file)
    print(f"Loaded new tools: {len(df_new)} tools")
except FileNotFoundError:
    print(f"\nERROR: {new_tools_file} not found!")
    sys.exit(1)

# Merge
print("\nMerging...")
df_combined = pd.concat([df_existing, df_new], ignore_index=True)
print(f"Combined: {len(df_combined)} tools")

# Deduplicate
print("Deduplicating...")
df_final = df_combined.drop_duplicates(subset=['Vendor Name'], keep='first')
duplicates_removed = len(df_combined) - len(df_final)
print(f"Removed {duplicates_removed} duplicates")
print(f"Final count: {len(df_final)} tools")

# Save
output_file = 'merged_pref_top50_updated.csv'
df_final.to_csv(output_file, index=False)

print(f"\n[OK] Merged database saved: {output_file}")

# Update index.html to use the merged file (if needed)
print("\n" + "="*80)
print("COMPLETE!")
print("="*80)
print(f"\nFinal database: {output_file}")
print(f"Total tools: {len(df_final)}")
print(f"New tools added: {len(df_new)}")
print(f"Duplicates removed: {duplicates_removed}")

print("\nYour index.html already uses this file.")
print("The web application will now show all tools with popularity rankings!")

# Create a summary report
summary = {
    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    'existing_tools': len(df_existing),
    'new_tools_extracted': len(df_new),
    'duplicates_removed': duplicates_removed,
    'final_total': len(df_final),
    'extraction_file': latest_extraction,
    'scored_file': new_tools_file if scored_files else 'N/A',
    'output_file': output_file
}

print(f"\nSummary:")
for key, value in summary.items():
    print(f"  {key}: {value}")
