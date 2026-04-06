#!/usr/bin/env python3
"""
Automated Logo Fetcher for Legal Tech Explorer

This script automatically downloads and processes vendor logos from their websites.
It tries favicon first, then parses the homepage for logo images.

Usage:
    python fetch_logos.py

Requirements:
    pip install requests beautifulsoup4 pillow python-slugify pandas
"""

import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse
from io import BytesIO

import requests
from bs4 import BeautifulSoup
from PIL import Image
from slugify import slugify
import pandas as pd


# Configuration
CSV_FILE = "merged_pref_top50.csv"
LOGOS_DIR = "logos"
LOGO_SIZE = (256, 256)  # Target size for logos
TIMEOUT = 10  # HTTP request timeout in seconds
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def normalize_url(url):
    """Normalize a URL by adding https:// if missing."""
    if not url:
        return None

    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    return url


def get_base_domain(url):
    """Extract base domain from URL (e.g., https://example.com)."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def slugify_vendor_name(vendor_name):
    """
    Create a filesystem-safe slug from vendor name.
    Removes spaces and special characters.
    """
    if not vendor_name:
        return None

    # Use python-slugify for safe filename
    return slugify(vendor_name, separator='')


def logo_exists(vendor_name, logos_dir):
    """Check if a logo already exists for this vendor."""
    slug = slugify_vendor_name(vendor_name)
    if not slug:
        return False

    # Check for any extension (.png, .jpg, .jpeg, .webp)
    for ext in ['.png', '.jpg', '.jpeg', '.webp']:
        logo_path = Path(logos_dir) / f"{slug}{ext}"
        if logo_path.exists():
            return True

    return False


def download_image(url, session):
    """Download an image from URL and return PIL Image object."""
    try:
        response = session.get(url, timeout=TIMEOUT, stream=True)
        response.raise_for_status()

        # Check if it's actually an image
        content_type = response.headers.get('Content-Type', '')
        if not content_type.startswith('image/'):
            return None

        # Load image into PIL
        img_data = BytesIO(response.content)
        img = Image.open(img_data)

        # Verify it's a valid image
        img.verify()

        # Reload image after verify (verify() closes the file)
        img_data.seek(0)
        img = Image.open(img_data)

        return img

    except Exception as e:
        # Silently fail - we'll try other methods
        return None


def try_favicon(base_url, session):
    """Try to download favicon.ico from the base domain."""
    favicon_url = urljoin(base_url, '/favicon.ico')
    return download_image(favicon_url, session)


def score_logo_candidate(img_tag, vendor_name):
    """
    Score an <img> tag based on how likely it is to be a logo.
    Higher score = more likely to be the logo.
    """
    score = 0

    # Get attributes
    src = img_tag.get('src', '').lower()
    alt = img_tag.get('alt', '').lower()
    class_attr = ' '.join(img_tag.get('class', [])).lower()
    id_attr = img_tag.get('id', '').lower()

    # Combine all text for searching
    all_text = f"{src} {alt} {class_attr} {id_attr}"

    # Check for "logo" keyword (strong indicator)
    if 'logo' in all_text:
        score += 100

    # Check for vendor name
    vendor_words = vendor_name.lower().split()
    for word in vendor_words:
        if len(word) > 3 and word in all_text:  # Skip short words
            score += 50

    # Prefer images in header/nav
    parent_tag = img_tag.parent.name if img_tag.parent else ''
    if parent_tag in ['header', 'nav']:
        score += 30

    # Penalize social media icons
    if any(social in all_text for social in ['facebook', 'twitter', 'linkedin', 'instagram', 'youtube']):
        score -= 100

    # Penalize very small images (likely icons)
    width = img_tag.get('width')
    height = img_tag.get('height')
    if width and height:
        try:
            w = int(re.sub(r'[^\d]', '', str(width)))
            h = int(re.sub(r'[^\d]', '', str(height)))
            if w < 50 or h < 50:
                score -= 50
        except:
            pass

    return score


def find_logo_on_page(homepage_url, vendor_name, session):
    """Parse homepage HTML to find the best logo candidate."""
    try:
        response = session.get(homepage_url, timeout=TIMEOUT)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all <img> tags
        img_tags = soup.find_all('img')

        if not img_tags:
            return None

        # Score each image
        candidates = []
        for img_tag in img_tags:
            src = img_tag.get('src')
            if not src:
                continue

            score = score_logo_candidate(img_tag, vendor_name)

            # Convert relative URLs to absolute
            absolute_url = urljoin(homepage_url, src)

            candidates.append({
                'url': absolute_url,
                'score': score,
                'img_tag': img_tag
            })

        # Sort by score (highest first)
        candidates.sort(key=lambda x: x['score'], reverse=True)

        # Try to download top candidates
        for candidate in candidates[:5]:  # Try top 5 candidates
            if candidate['score'] <= 0:
                continue

            img = download_image(candidate['url'], session)
            if img:
                return img

        return None

    except Exception as e:
        return None


def process_image(img, target_size=LOGO_SIZE):
    """
    Process image to standard format:
    - Convert to RGBA
    - Crop transparent/white borders to get actual logo bounds
    - Resize to fill as much of target_size as possible while maintaining aspect ratio
    - Center on transparent background
    """
    # Convert to RGBA
    if img.mode != 'RGBA':
        if img.mode == 'P' and 'transparency' in img.info:
            img = img.convert('RGBA')
        elif img.mode == 'RGB':
            img = img.convert('RGBA')
        else:
            img = img.convert('RGBA')

    # Crop to actual content (remove transparent/white borders)
    try:
        # Get the bounding box of non-transparent content
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
    except:
        pass  # If getbbox fails, use original image

    # Calculate scaling to maximize size while fitting within target
    # Use a padding of 5% to avoid logos touching edges
    padding_factor = 0.95
    max_width = int(target_size[0] * padding_factor)
    max_height = int(target_size[1] * padding_factor)

    # Calculate scale factors for both dimensions
    width_scale = max_width / img.width
    height_scale = max_height / img.height

    # Use the smaller scale to ensure we fit within bounds
    scale = min(width_scale, height_scale)

    # Calculate new size
    new_width = int(img.width * scale)
    new_height = int(img.height * scale)

    # Resize with high quality
    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Create transparent canvas
    canvas = Image.new('RGBA', target_size, (0, 0, 0, 0))

    # Calculate position to center the image
    x = (target_size[0] - img.width) // 2
    y = (target_size[1] - img.height) // 2

    # Paste image onto canvas
    canvas.paste(img, (x, y), img if img.mode == 'RGBA' else None)

    return canvas


def save_logo(img, vendor_name, logos_dir):
    """Save processed logo to disk."""
    slug = slugify_vendor_name(vendor_name)
    if not slug:
        return False

    logo_path = Path(logos_dir) / f"{slug}.png"

    try:
        img.save(logo_path, 'PNG')
        return True
    except Exception as e:
        print(f"  ❌ Error saving logo: {e}")
        return False


def fetch_logo_for_vendor(vendor_name, vendor_website, logos_dir, session):
    """
    Attempt to fetch and save logo for a single vendor.
    Returns: (success: bool, method: str)
    """
    if logo_exists(vendor_name, logos_dir):
        return (False, 'already_exists')

    if not vendor_website:
        return (False, 'no_website')

    # Normalize URL
    url = normalize_url(vendor_website)
    if not url:
        return (False, 'invalid_url')

    base_url = get_base_domain(url)

    # Try Method 1: Favicon
    print(f"  🔍 Trying favicon for {vendor_name}...")
    img = try_favicon(base_url, session)

    if img:
        method = 'favicon'
    else:
        # Try Method 2: Parse homepage
        print(f"  🔍 Parsing homepage for {vendor_name}...")
        img = find_logo_on_page(url, vendor_name, session)
        method = 'homepage' if img else None

    if not img:
        return (False, 'not_found')

    # Process and save image
    try:
        processed_img = process_image(img)
        success = save_logo(processed_img, vendor_name, logos_dir)

        if success:
            return (True, method)
        else:
            return (False, 'save_failed')

    except Exception as e:
        print(f"  ❌ Error processing image: {e}")
        return (False, 'processing_failed')


def main():
    """Main execution function."""
    print("=" * 70)
    print("Legal Tech Explorer - Automated Logo Fetcher")
    print("=" * 70)
    print()

    # Verify files exist
    if not Path(CSV_FILE).exists():
        print(f"❌ Error: CSV file '{CSV_FILE}' not found!")
        return

    # Create logos directory if it doesn't exist
    Path(LOGOS_DIR).mkdir(exist_ok=True)

    # Load CSV
    print(f"📂 Loading vendors from {CSV_FILE}...")
    df = pd.read_csv(CSV_FILE)

    print(f"✓ Found {len(df)} vendors")
    print()

    # Create session with retry and custom headers
    session = requests.Session()
    session.headers.update({'User-Agent': USER_AGENT})

    # Adapter with retries
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # Stats
    stats = {
        'already_exists': 0,
        'favicon': 0,
        'homepage': 0,
        'failed': 0,
        'no_website': 0
    }

    # Process each vendor
    print("🚀 Starting logo fetch...")
    print()

    for idx, row in df.iterrows():
        vendor_name = row.get('Vendor Name', '')
        vendor_website = row.get('Vendor Website', '')

        if not vendor_name:
            continue

        print(f"[{idx + 1}/{len(df)}] {vendor_name}")

        success, method = fetch_logo_for_vendor(
            vendor_name,
            vendor_website,
            LOGOS_DIR,
            session
        )

        if success:
            stats[method] += 1
            print(f"  ✓ Logo saved via {method}")
        elif method == 'already_exists':
            stats['already_exists'] += 1
            print(f"  ⏭️  Logo already exists, skipping")
        elif method == 'no_website':
            stats['no_website'] += 1
            print(f"  ⚠️  No website URL provided")
        else:
            stats['failed'] += 1
            print(f"  ❌ Could not find logo for {vendor_name} ({vendor_website})")

        print()

        # Small delay to be respectful to servers
        time.sleep(0.5)

    # Print summary
    print()
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Already existed:     {stats['already_exists']}")
    print(f"Downloaded (favicon): {stats['favicon']}")
    print(f"Downloaded (homepage): {stats['homepage']}")
    print(f"No website:          {stats['no_website']}")
    print(f"Failed:              {stats['failed']}")
    print()
    total_new = stats['favicon'] + stats['homepage']
    print(f"✓ Successfully downloaded {total_new} new logos!")
    print()


if __name__ == "__main__":
    main()
