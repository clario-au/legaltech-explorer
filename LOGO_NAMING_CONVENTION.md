# Logo Naming Convention

## How Logo Matching Works

The Legal-Tech Explorer automatically matches vendor logos based on the **Vendor Name** field in your CSV database. The system uses the following naming convention:

### Format
Logo files should be named using the **slug format**:
- **Lowercase only**
- **Remove all spaces**
- **Remove all special characters** (hyphens, dots, commas, etc.)
- **Keep only letters and numbers**

### Examples

| Vendor Name in CSV | Logo Filename |
|-------------------|---------------|
| Ace4 AI | `ace4ai.png` |
| Onit, Inc. | `onitinc.png` |
| Newcode.ai | `newcodeai.png` |
| Dioptra | `dioptra.png` |
| Adobe | `adobe.png` |
| Thomson Reuters | `thomsonreuters.png` |

### File Extensions
The system supports the following image formats:
- `.png` (recommended)
- `.jpg`
- `.jpeg`
- `.webp`

### Image Specifications
- **Size**: 256x256 pixels (square)
- **Format**: PNG with transparent background (recommended)
- **Content**: Logo should be centered and scaled to fill most of the canvas

## Adding New Logos

### Method 1: Manual Naming
1. Get the vendor name from your CSV (column: "Vendor Name")
2. Convert to slug format:
   - Convert to lowercase
   - Remove all spaces and special characters
   - Keep only letters and numbers
3. Save as `[slug].png` in the `logos/` folder

**Example:**
- Vendor Name: "Legal Mike AI"
- Slug: "legalmikeai"
- Filename: `legalmikeai.png`

### Method 2: Using fetch_logos.py
The `fetch_logos.py` script automatically:
1. Reads vendor names from your CSV
2. Searches for logos online
3. Downloads and saves them with the correct naming convention
4. Processes images to 256x256 with transparent background

### Method 3: Bulk Rename
If you have logos with incorrect names, use the `rename_logos.py` script:
```bash
python rename_logos.py
```

This will automatically rename all logo files in the `logos/` folder to match the correct convention.

## Troubleshooting

### Logo Not Appearing?
1. **Check the vendor name in CSV**: The logo filename must match the "Vendor Name" column
2. **Verify filename format**: Use the slug format (lowercase, alphanumeric only)
3. **Check file extension**: Use `.png`, `.jpg`, `.jpeg`, or `.webp`
4. **Test the conversion**:
   ```python
   import re
   vendor_name = "Your Vendor Name"
   slug = re.sub(r'[^a-z0-9]', '', vendor_name.lower())
   print(f"Expected filename: {slug}.png")
   ```

### Multiple Products from Same Vendor?
The logo system uses the **Vendor Name** field, not the Product Name. All products from the same vendor will share the same logo.

For example:
- Vendor: "Microsoft"
- Products: "Microsoft Copilot", "Microsoft Teams", "Microsoft 365"
- Logo file: `microsoft.png` (used for all three)

## Technical Details

The logo matching logic (from `index.html`):
```javascript
function vendorSlug(name) {
  return String(name||'').toLowerCase().replace(/[^a-z0-9]/g,'');
}

function logoCandidates(name) {
  var slug = vendorSlug(name);
  return [
    'logos/' + slug + '.png',
    'logos/' + slug + '.jpg',
    'logos/' + slug + '.jpeg',
    'logos/' + slug + '.webp'
  ];
}
```

The system tries each file extension in order until it finds a match. If no logo is found, it displays an initials badge instead.
