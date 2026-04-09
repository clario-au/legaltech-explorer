"""
Rename vendors to be more succinct while maintaining logo alignment.
"""

import pandas as pd
import sys

# Fix UTF-8 encoding on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    """Main execution."""

    print("="*80)
    print("RENAMING VENDORS FOR SUCCINCTNESS")
    print("="*80)

    # Load database
    database_file = 'merged_pref_top50_updated.csv'

    try:
        df = pd.read_csv(database_file)
        print(f"\nLoaded: {database_file}")
        print(f"Total tools: {len(df)}")
    except FileNotFoundError:
        print(f"\nERROR: {database_file} not found!")
        return

    # Define renaming map (old name -> new name)
    # Logo names will stay the same since they're based on the slugified old names
    rename_map = {
        'Saga International B.V.': 'Saga AI Platform',
        'The Simple Associate, Inc., dba Briefpoint': 'Briefpoint',
        'Rev': 'Rev',  # Keep as is, just remove product description from Product Name if needed
        'eDiscovery AI': 'eDiscovery AI',  # Keep vendor name, clean product name
        'Newcode.ai': 'Newcode.ai',  # Keep as is
        'Ruli, Inc.': 'Ruli',
        'LegalSifter, Inc.': 'LegalSifter',
        'Kelsen Legal Technologies Inc.': 'Kelsen',
        'BRYTER GmbH': 'BRYTER',
        'Competition AI': 'Competition AI',  # Keep as is
        'CTRL AI Global Ltd.': 'CTRL AI',
        'Bigle Iberia, S.L.': 'Bigle',
        'Laine Neural Network SA': 'Laine',
        'ContractPodAI': 'LEAH',
        'Erbis': 'Erbis',  # Keep as is
        'ClearPeople': 'ClearPeople',  # Keep as is
        'A-dapt International Ltd': 'A-dapt',
        'Upland Software': 'Upland Software',  # Keep as is
        'ClauseBase 9': 'Clause9',
        'Lexlink AI': 'LexiLink',
        'Oddr': 'Oddr',  # Already correct
        'Sonar Legal': 'Sonar Legal',  # Keep as is
        'CircleUp Technologies Pty Ltd': 'GoCircl',
        'Casey': 'Casey',  # Keep as is
        'Luminos.AI': 'Luminos',
        'ELTEMATE A Hogan Lovells Technology Company': 'CRAIG',
        # Second batch
        'Agiloft': 'Agiloft',  # Remove product name from vendor
        'DocuSign': 'DocuSign',  # Remove product name from vendor
        'Luminance Technologies Ltd.': 'Luminance',
        'Ironclad, Inc.': 'Ironclad',
        'Robin AI Limited': 'Robin AI',
    }

    # Track changes
    changes_made = []

    # Apply renames
    for old_name, new_name in rename_map.items():
        mask = df['Vendor Name'] == old_name
        if mask.any():
            df.loc[mask, 'Vendor Name'] = new_name
            count = mask.sum()
            changes_made.append((old_name, new_name, count))
            print(f"✓ Renamed: '{old_name}' → '{new_name}' ({count} tools)")

    # Backup original
    if changes_made:
        backup_file = database_file.replace('.csv', '_backup_before_rename.csv')
        pd.read_csv(database_file).to_csv(backup_file, index=False)

        # Save updated database
        df.to_csv(database_file, index=False)

        print(f"\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}")
        print(f"Total vendors renamed: {len(changes_made)}")
        print(f"Total tools affected: {sum(c[2] for c in changes_made)}")
        print(f"\nBackup saved: {backup_file}")
        print(f"Updated database: {database_file}")

        print(f"\n{'='*80}")
        print("CHANGES MADE")
        print(f"{'='*80}")
        print(f"{'Old Name':<50} {'New Name':<30} {'Tools'}")
        print("-"*80)
        for old, new, count in changes_made:
            print(f"{old:<50} {new:<30} {count}")

        print(f"\n{'='*80}")
        print("NEXT STEPS")
        print(f"{'='*80}")
        print("1. Run update_html_data.py to update the web UI")
        print("2. Logos will still work (they're based on slugified old names)")
        print("3. Run list_all_logo_names.py to see updated logo requirements")

    else:
        print("\nNo vendors found matching the rename list.")

if __name__ == "__main__":
    main()
