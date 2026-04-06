# Logo Fetcher - Automated Logo Collection

This script automatically downloads and processes vendor logos from their websites for the Legal Tech Explorer project.

## What it does

For each vendor in `merged_pref_top50.csv`, the script:

1. **Checks if logo already exists** - Skips vendors that already have logos in `logos/`
2. **Tries favicon** - Attempts to download `favicon.ico` from the vendor's domain
3. **Parses homepage** - If favicon fails, it scrapes the vendor's homepage to find logo images
4. **Processes images** - Standardizes all logos to 256x256 PNG with transparent background
5. **Saves logos** - Saves as `logos/<slugified-vendor-name>.png`

## Installation

```bash
# Activate your virtual environment
cd database_ui
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements_logos.txt
```

## Usage

```bash
# Run the script
python fetch_logos.py
```

The script will:
- Show progress for each vendor
- Display which method was used (favicon or homepage)
- Log any failures
- Provide a summary at the end

## Output Example

```
======================================================================
Legal Tech Explorer - Automated Logo Fetcher
======================================================================

📂 Loading vendors from merged_pref_top50.csv...
✓ Found 242 vendors

🚀 Starting logo fetch...

[1/242] Actionstep
  ⏭️  Logo already exists, skipping

[43/242] NewVendor
  🔍 Trying favicon for NewVendor...
  ✓ Logo saved via favicon

[44/242] AnotherVendor
  🔍 Trying favicon for AnotherVendor...
  🔍 Parsing homepage for AnotherVendor...
  ✓ Logo saved via homepage

[45/242] FailedVendor
  🔍 Trying favicon for FailedVendor...
  🔍 Parsing homepage for FailedVendor...
  ❌ Could not find logo for FailedVendor (https://example.com)

======================================================================
Summary
======================================================================
Already existed:      42
Downloaded (favicon): 120
Downloaded (homepage): 65
No website:           0
Failed:               15

✓ Successfully downloaded 185 new logos!
```

## How it works

### Logo Detection

The script uses a scoring system to find the best logo on a webpage:

- **+100 points** - Image contains "logo" in src/alt/class/id
- **+50 points** - Image contains vendor name
- **+30 points** - Image is in `<header>` or `<nav>` tag
- **-100 points** - Image appears to be social media icon
- **-50 points** - Image is very small (likely an icon)

### Image Processing

All logos are standardized:
1. Converted to RGBA (supports transparency)
2. Resized to fit within 256x256 while maintaining aspect ratio
3. Centered on transparent 256x256 canvas
4. Saved as PNG

### Filename Slugification

Vendor names are converted to safe filenames:
- `"Adobe Acrobat"` → `adobeacrobat.png`
- `"iManage LLC"` → `imanagellc.png`
- `"Contracts365"` → `contracts365.png`

## Idempotency

The script is **safe to run multiple times**:
- It checks for existing logos before downloading
- Failed vendors can be re-attempted by running the script again
- No logos will be overwritten

## Troubleshooting

### Logo not found
Some vendors may not have easily detectable logos. For these:
1. Check the output for the vendor name
2. Manually download their logo from their website
3. Save it as `logos/<slugified-name>.png`
4. Run the script again (it will skip this vendor)

### Rate limiting
The script includes:
- 0.5 second delay between requests
- Retry logic for failed requests
- Respectful User-Agent header

If you encounter rate limiting, you can increase the delay in `fetch_logos.py` (line 44):
```python
time.sleep(0.5)  # Increase this value
```

### Invalid images
Some sites may return invalid image data. The script handles this gracefully and logs the failure.

## Manual tweaking

You can adjust the logo detection scoring in the `score_logo_candidate()` function to:
- Prefer different keywords
- Adjust size thresholds
- Add custom vendor-specific logic

## Files created

- `fetch_logos.py` - Main script
- `requirements_logos.txt` - Python dependencies
- `LOGO_FETCHER_README.md` - This file
