import pandas as pd
from pathlib import Path

# Find the latest Google Trends file
trends_files = list(Path('.').glob('google_trends_results_*.csv'))
latest_file = sorted(trends_files)[-1]
print(f'Using file: {latest_file}\n')

df = pd.read_csv(latest_file)

print('Google Trends Data Summary')
print('='*80)
print(f'\nTotal tools: {len(df)}')
print(f'Successful: {sum(df["status"] == "success")}')
print(f'No data: {sum(df["status"] == "no_data")}')
print(f'Failed: {sum(df["status"] == "failed")}')

print(f'\nColumns collected:')
for col in df.columns:
    print(f'  - {col}')

print(f'\nSample data (first 10 successful):')
successful = df[df["status"] == "success"].head(10)
for idx, row in successful.iterrows():
    print(f'  {row["Vendor Name"]:30s}: avg={row["avg_interest"]:5.1f}, peak={row["peak_interest"]:3.0f}, query="{row["query"]}"')

print(f'\nScore distribution (successful tools only):')
successful_all = df[df["status"] == "success"]
print(f'  Min:    {successful_all["avg_interest"].min():.1f}')
print(f'  Max:    {successful_all["avg_interest"].max():.1f}')
print(f'  Mean:   {successful_all["avg_interest"].mean():.1f}')
print(f'  Median: {successful_all["avg_interest"].median():.1f}')

print(f'\nTop 10 tools by average interest:')
top10 = df[df["status"] == "success"].nlargest(10, 'avg_interest')
for idx, row in top10.iterrows():
    print(f'  {row["Vendor Name"]:30s}: {row["avg_interest"]:5.1f} (peak: {row["peak_interest"]:3.0f})')
