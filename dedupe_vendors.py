import pandas as pd
import sys

def dedupe_vendors():
    """Extract vendor names from legal_tools_all.xlsx that don't appear in merged_pref_top50.csv"""

    try:
        # Read the Excel file
        print("Reading legal_tools_all.xlsx...")
        legal_tools_df = pd.read_excel('legal_tools_all.xlsx')

        # Read the CSV file
        print("Reading merged_pref_top50.csv...")
        merged_pref_df = pd.read_csv('merged_pref_top50.csv')

        # Print column names to verify
        print(f"\nColumns in legal_tools_all.xlsx: {legal_tools_df.columns.tolist()}")
        print(f"Columns in merged_pref_top50.csv: {merged_pref_df.columns.tolist()}")

        # Try to identify the vendor name column (could be 'Vendor Name', 'Name', 'Company', etc.)
        legal_tools_name_col = None
        for col in legal_tools_df.columns:
            if 'vendor' in col.lower() or 'name' in col.lower() or 'company' in col.lower():
                legal_tools_name_col = col
                break

        if legal_tools_name_col is None:
            legal_tools_name_col = legal_tools_df.columns[0]
            print(f"\nWarning: Couldn't find vendor column, using first column: {legal_tools_name_col}")

        # Get vendor names from both sources
        legal_tools_vendors = set(legal_tools_df[legal_tools_name_col].dropna().astype(str).str.strip())
        merged_pref_vendors = set(merged_pref_df['Vendor Name'].dropna().astype(str).str.strip())

        print(f"\nTotal vendors in legal_tools_all.xlsx: {len(legal_tools_vendors)}")
        print(f"Total vendors in merged_pref_top50.csv: {len(merged_pref_vendors)}")

        # Find vendors that are in legal_tools but NOT in merged_pref
        unique_vendors = legal_tools_vendors - merged_pref_vendors

        print(f"Vendors in legal_tools_all but NOT in merged_pref_top50: {len(unique_vendors)}")

        # Create a DataFrame with the unique vendors
        result_df = pd.DataFrame(sorted(unique_vendors), columns=['Vendor Name'])

        # Save to CSV
        output_file = 'unique_vendors_not_in_merged_pref.csv'
        result_df.to_csv(output_file, index=False)

        print(f"\n✓ Successfully created {output_file}")
        print(f"\nFirst 10 unique vendors:")
        for i, vendor in enumerate(result_df['Vendor Name'].head(10), 1):
            print(f"  {i}. {vendor}")

        return output_file

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    dedupe_vendors()
