"""
Rename logo files to match the naming convention used by the web app.
The web app expects logos in slug format: lowercase, alphanumeric only.
"""
import os
import re
from pathlib import Path

def vendor_slug(name):
    """Convert vendor name to slug format (lowercase, alphanumeric only)"""
    return re.sub(r'[^a-z0-9]', '', str(name).lower())

def main():
    logos_dir = Path('logos')
    if not logos_dir.exists():
        print("Error: logos/ directory not found")
        return

    renamed_count = 0
    skipped_count = 0

    # Get all image files in logos directory
    for logo_file in logos_dir.glob('*'):
        if logo_file.suffix.lower() not in ['.png', '.jpg', '.jpeg', '.webp']:
            continue

        # Get the current filename without extension
        current_name = logo_file.stem
        current_ext = logo_file.suffix

        # Convert to slug format
        slug_name = vendor_slug(current_name)
        new_filename = slug_name + current_ext.lower()
        new_path = logos_dir / new_filename

        # Check if rename is needed
        if logo_file.name == new_filename:
            print(f"[OK] Already correct: {logo_file.name}")
            skipped_count += 1
            continue

        # Check if target file already exists
        if new_path.exists():
            print(f"[SKIP] Conflict: {logo_file.name} -> {new_filename} (target exists)")
            skipped_count += 1
            continue

        # Rename the file
        try:
            logo_file.rename(new_path)
            print(f"[RENAMED] {logo_file.name} -> {new_filename}")
            renamed_count += 1
        except Exception as e:
            print(f"[ERROR] Failed to rename {logo_file.name}: {e}")

    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Renamed: {renamed_count} files")
    print(f"  Skipped: {skipped_count} files")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()
