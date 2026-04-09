# Google Trends Integration - Safe Implementation Guide

This document explains the safe, rate-limited approach to collecting and integrating Google Trends data into the popularity scoring system.

## Overview

The system consists of two main scripts:

1. **`google_trends_collector.py`** - Safely collects Trends data with robust rate limiting
2. **`integrate_trends_into_popularity.py`** - Normalizes and integrates Trends into popularity scores

## Safety Features

### A. Rate Limiting and Backoff

✅ **Strict global rate limiter**
- Max 50 requests/hour (configurable)
- Max 400 requests/day (configurable)
- 5-second minimum delay between requests
- Tracks hourly and daily counters

✅ **Exponential backoff with jitter on 429 errors**
- Initial backoff: 60 seconds
- Multiplier: 2x per retry
- Max backoff: 1 hour
- ±20% random jitter to avoid thundering herd

✅ **Hard stop on repeated 429s**
- Stops after 5x 429 errors in a single run
- Prevents "fighting" rate limits

✅ **CAPTCHA detection**
- Treats CAPTCHA as hard stop (fail closed)
- Requires manual intervention

### B. Auditability and Governance

✅ **Comprehensive logging**
- Every request logged with timestamp, query, status code, backoff applied
- Logs saved to `logs/google_trends_YYYYMMDD_HHMMSS.log`
- Both file and console output

✅ **Hard safety caps**
- Configurable max requests per hour/day
- Max retries per tool (default: 3)
- Max 429 errors per run (default: 5)

✅ **Kill switch**
- `CONFIG["enabled"]` flag in code
- Set to `False` to instantly disable all Trends collection

### C. Data Quality

✅ **Handles sparse/missing data**
- Tools with "not enough data" get fallback score (median of valid scores)
- Configurable: treat as missing (None) or assign neutral score

✅ **Query disambiguation**
- Uses Vendor Name primarily, falls back to Product Name
- Optional keyword modifiers (e.g., "+ legal tech") - currently disabled

✅ **Normalization**
- Trends scores (0-100 within timeframe) are re-normalized across all tools
- Missing scores filled with median of valid scores
- Proper handling of edge cases (all identical scores, all missing, etc.)

## Configuration

Edit `google_trends_collector.py` to adjust:

```python
CONFIG = {
    # Kill switch
    "enabled": True,  # Set to False to disable

    # Rate limiting (CONSERVATIVE)
    "min_delay_between_requests": 5.0,  # seconds
    "max_requests_per_hour": 50,
    "max_requests_per_day": 400,

    # Backoff
    "initial_backoff": 60,
    "max_backoff": 3600,
    "backoff_multiplier": 2,

    # Retries
    "max_retries_per_tool": 3,
    "max_429_errors_per_run": 5,

    # Trends parameters
    "timeframe": "today 12-m",  # Last 12 months
    "geo": "",  # Worldwide (use "AU" for Australia)
}
```

## Usage

### Step 1: Install Dependencies

```bash
pip install pytrends pandas numpy
```

### Step 2: Collect Trends Data

```bash
python google_trends_collector.py
```

**Expected behavior:**
- Takes ~40-50 minutes for 431 tools (5 seconds per tool minimum)
- Creates `google_trends_results_YYYYMMDD_HHMMSS.csv`
- Creates detailed log in `logs/`

**What to watch for:**
- If you see 429 errors, the script will automatically back off
- If you hit 5x 429 errors, the script will stop (check logs)
- If you see CAPTCHA, the script will stop immediately

**If blocked:**
1. Check the logs to see what triggered it
2. Wait 24 hours before retrying
3. Consider reducing `max_requests_per_hour` (try 25)
4. Consider increasing `min_delay_between_requests` (try 10)

### Step 3: Integrate into Popularity

```bash
python integrate_trends_into_popularity.py
```

This will:
- Find the most recent Trends results file
- Normalize scores across all tools
- Calculate enhanced popularity scores with new weights:
  - Adoption Level: 30% (was 40%)
  - Maturity: 20% (was 25%)
  - AI-Powered: 10% (was 15%)
  - Regions: 8% (was 10%)
  - Completeness: 7% (was 10%)
  - **Google Trends: 25%** (NEW)
- Update `merged_pref_top50_updated.csv`
- Create timestamped backup

### Step 4: Update Web UI

```bash
python update_html_data.py
```

This updates `index.html` with the new popularity scores.

## Understanding the Output

### Trends Results File

Columns:
- `Vendor Name`, `Product Name` - Tool identifiers
- `trends_score` - Average interest (0-100) over timeframe
- `query` - Search query used
- `status` - success / no_data / failed
- `avg_interest` - Mean of interest over time
- `peak_interest` - Peak interest value
- `timeframe`, `geo` - Collection parameters

### Log File

Example entries:
```
2025-12-27 10:15:23 | INFO | Querying Trends for: 'Clio' (attempt 1)
2025-12-27 10:15:28 | INFO | ✓ Success: avg=45.23, peak=67.00
2025-12-27 10:15:33 | INFO | Querying Trends for: 'SmallVendor' (attempt 1)
2025-12-27 10:15:38 | WARNING | No data for 'SmallVendor' - treating as sparse/missing
2025-12-27 10:15:43 | WARNING | 429 error - backing off for 63s
```

## Troubleshooting

### Problem: Too many 429 errors

**Solution:**
1. Reduce `max_requests_per_hour` from 50 to 25
2. Increase `min_delay_between_requests` from 5 to 10
3. Wait 24 hours before next attempt

### Problem: CAPTCHA appeared

**Solution:**
1. This is expected if Google detects automation
2. Wait 24 hours minimum
3. Consider using a different network/IP
4. Reduce request rate significantly

### Problem: "No data" for many tools

**Solution:**
- This is normal for smaller/niche vendors
- The integration script fills these with median score
- Consider adding "+ legal tech" to queries for disambiguation (edit `_build_query()`)

### Problem: Want faster collection

**Don't** reduce delays below current conservative settings without monitoring for blocks.

**Do** consider:
- Running overnight (takes ~40 min for 431 tools)
- Splitting into batches and running across days
- Adding resume capability (manual edit required)

## Future Enhancements

Potential improvements:

1. **Resume capability** - Save progress, allow resuming from interruption
2. **Regional comparison** - Collect both worldwide and AU-specific data
3. **Keyword disambiguation** - Add "legal tech" or other modifiers to queries
4. **Historical tracking** - Re-collect monthly to track trend changes
5. **Related queries** - Use Trends' related queries API for brand insights

## File Structure

```
database_ui/
├── google_trends_collector.py           # Main collection script
├── integrate_trends_into_popularity.py  # Integration script
├── GOOGLE_TRENDS_README.md             # This file
├── logs/
│   └── google_trends_YYYYMMDD_HHMMSS.log
├── google_trends_results_YYYYMMDD_HHMMSS.csv
└── merged_pref_top50_updated.csv       # Updated with Trends
```

## Important Notes

⚠️ **DO NOT:**
- Run multiple collection processes in parallel (local + CI + Render)
- Reduce delays below 5 seconds without testing
- Retry immediately after getting blocked
- Disable safety caps without understanding implications

✅ **DO:**
- Monitor logs for 429 errors and CAPTCHA
- Start with conservative settings
- Wait 24 hours if blocked
- Keep kill switch accessible
- Test with small subset first (edit df to df.head(10))

## Testing

Before full collection, test with a small subset:

1. Edit `google_trends_collector.py`:
   ```python
   df = pd.read_csv(db_file)
   df = df.head(10)  # Test with first 10 tools
   ```

2. Run collection:
   ```bash
   python google_trends_collector.py
   ```

3. Check logs for any issues

4. If successful, remove the `.head(10)` limit and run full collection

## Contact

If you encounter persistent blocking or need to adjust strategy, consider:
- Reducing request volume significantly (20/hour)
- Using Google Trends API (requires quota/billing)
- Accepting lower coverage (collect for top N tools only)
- Using alternative popularity signals (website traffic, GitHub stars, etc.)
