import pandas as pd

df = pd.read_csv('merged_pref_top50_updated.csv')
aus_tools = df[df['Hosting Location'].str.contains('Australia', case=False, na=False)]

print(f'Tools hosted in Australia: {len(aus_tools)}')
print('\nAustralian-hosted tools:')
for idx, row in aus_tools[['Vendor Name', 'Hosting Location']].iterrows():
    print(f'  - {row["Vendor Name"]}: {row["Hosting Location"]}')
