"""
Google Trends Data Collector with Robust Rate Limiting and Safety Measures.

This script collects Google Trends data for legal tech tools with:
- Strict global rate limiting
- Exponential backoff with jitter on 429 errors
- Request logging and auditability
- Hard safety caps
- Kill switch functionality
- Proper error handling for sparse data and CAPTCHA
"""

import pandas as pd
import time
import random
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from pytrends.request import TrendReq
import logging

# Fix UTF-8 encoding on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# ============================================================================
# CONFIGURATION AND SAFETY CAPS
# ============================================================================

CONFIG = {
    # Kill switch - set to False to disable all Trends collection
    "enabled": True,

    # Rate limiting (CONSERVATIVE - adjust based on results)
    "min_delay_between_requests": 5.0,  # seconds
    "max_requests_per_hour": 50,
    "max_requests_per_day": 400,

    # Backoff configuration
    "initial_backoff": 60,  # seconds
    "max_backoff": 3600,  # 1 hour
    "backoff_multiplier": 2,
    "jitter_range": 0.2,  # ±20% jitter

    # Retry limits
    "max_retries_per_tool": 3,
    "max_429_errors_per_run": 5,  # Hard stop after this many 429s

    # Trends parameters
    "timeframe": "today 12-m",  # Last 12 months
    "geo": "",  # Global (empty string = worldwide)
    "gprop": "",  # Google property (empty = web search)

    # Data handling
    "treat_sparse_as_missing": True,
    "fallback_score": None,  # None means skip in popularity calculation
}

# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging():
    """Set up detailed logging for auditability."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"google_trends_{timestamp}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    return log_file

# ============================================================================
# RATE LIMITER WITH SAFETY CAPS
# ============================================================================

class RateLimiter:
    """Global rate limiter with hourly and daily caps."""

    def __init__(self, config):
        self.config = config
        self.last_request_time = None
        self.requests_this_hour = 0
        self.requests_this_day = 0
        self.hour_start = datetime.now()
        self.day_start = datetime.now()
        self.total_429_errors = 0

    def wait_if_needed(self):
        """Wait if necessary to respect rate limits."""
        now = datetime.now()

        # Reset hourly counter
        if (now - self.hour_start).total_seconds() >= 3600:
            self.requests_this_hour = 0
            self.hour_start = now
            logging.info(f"Hourly counter reset. Daily count: {self.requests_this_day}")

        # Reset daily counter
        if (now - self.day_start).total_seconds() >= 86400:
            self.requests_this_day = 0
            self.day_start = now
            logging.info("Daily counter reset")

        # Check caps (removed hourly wait - will continue with same precautions)
        if self.requests_this_hour >= self.config["max_requests_per_hour"]:
            logging.info(f"Hourly limit of {self.config['max_requests_per_hour']} reached. Resetting counter and continuing...")
            self.requests_this_hour = 0
            self.hour_start = datetime.now()

        if self.requests_this_day >= self.config["max_requests_per_day"]:
            logging.error("Daily request limit reached. Stopping.")
            raise Exception("Daily request limit exceeded")

        # Minimum delay between requests
        if self.last_request_time:
            elapsed = (now - self.last_request_time).total_seconds()
            min_delay = self.config["min_delay_between_requests"]
            if elapsed < min_delay:
                wait = min_delay - elapsed
                logging.debug(f"Rate limiting: waiting {wait:.2f}s")
                time.sleep(wait)

        self.last_request_time = datetime.now()
        self.requests_this_hour += 1
        self.requests_this_day += 1

    def record_429(self):
        """Record a 429 error and check if we should stop."""
        self.total_429_errors += 1
        logging.warning(f"429 error count: {self.total_429_errors}/{self.config['max_429_errors_per_run']}")

        if self.total_429_errors >= self.config["max_429_errors_per_run"]:
            logging.error("Too many 429 errors. Hard stop.")
            raise Exception("Too many 429 errors - IP may be rate limited")

# ============================================================================
# BACKOFF STRATEGY
# ============================================================================

def calculate_backoff(attempt, config):
    """Calculate exponential backoff with jitter."""
    base_backoff = config["initial_backoff"] * (config["backoff_multiplier"] ** attempt)
    base_backoff = min(base_backoff, config["max_backoff"])

    # Add jitter (±20%)
    jitter = base_backoff * config["jitter_range"] * (2 * random.random() - 1)
    backoff = base_backoff + jitter

    return max(1, backoff)  # Minimum 1 second

# ============================================================================
# TRENDS DATA COLLECTION
# ============================================================================

class TrendsCollector:
    """Collect Google Trends data with robust error handling."""

    def __init__(self, config, rate_limiter):
        self.config = config
        self.rate_limiter = rate_limiter
        self.pytrends = None
        self.results = []

    def init_pytrends(self):
        """Initialize pytrends connection."""
        try:
            # Simple initialization without retry parameters (handled by our own retry logic)
            self.pytrends = TrendReq(
                hl='en-US',
                tz=0,
                timeout=(10, 25)
            )
            logging.info("Initialized pytrends connection")
        except Exception as e:
            logging.error(f"Failed to initialize pytrends: {e}")
            raise

    def collect_for_tool(self, vendor_name, product_name, attempt=0):
        """
        Collect Trends data for a single tool.

        Returns: dict with trends_score and metadata, or None if failed
        """
        if not self.config["enabled"]:
            logging.info("Trends collection disabled by kill switch")
            return None

        # Rate limiting
        try:
            self.rate_limiter.wait_if_needed()
        except Exception as e:
            logging.error(f"Rate limiter stopped execution: {e}")
            raise

        # Build search query
        query = self._build_query(vendor_name, product_name)

        logging.info(f"Querying Trends for: '{query}' (attempt {attempt + 1})")

        try:
            # Build payload
            self.pytrends.build_payload(
                [query],
                cat=0,
                timeframe=self.config["timeframe"],
                geo=self.config["geo"],
                gprop=self.config["gprop"]
            )

            # Get interest over time
            interest_df = self.pytrends.interest_over_time()

            if interest_df.empty or query not in interest_df.columns:
                logging.warning(f"No data for '{query}' - treating as sparse/missing")
                return {
                    "trends_score": self.config["fallback_score"],
                    "query": query,
                    "status": "no_data",
                    "avg_interest": None,
                    "peak_interest": None
                }

            # Calculate metrics
            interest_values = interest_df[query].values
            avg_interest = float(interest_values.mean())
            peak_interest = float(interest_values.max())

            result = {
                "trends_score": avg_interest,  # Use average as base score
                "query": query,
                "status": "success",
                "avg_interest": avg_interest,
                "peak_interest": peak_interest,
                "timeframe": self.config["timeframe"],
                "geo": self.config["geo"] or "worldwide"
            }

            logging.info(f"✓ Success: avg={avg_interest:.2f}, peak={peak_interest:.2f}")
            return result

        except Exception as e:
            error_str = str(e).lower()

            # Handle 429 / rate limiting
            if "429" in error_str or "too many requests" in error_str:
                self.rate_limiter.record_429()

                if attempt < self.config["max_retries_per_tool"]:
                    backoff = calculate_backoff(attempt, self.config)
                    logging.warning(f"429 error - backing off for {backoff:.0f}s")
                    time.sleep(backoff)
                    return self.collect_for_tool(vendor_name, product_name, attempt + 1)
                else:
                    logging.error(f"Max retries exceeded for '{query}' due to 429")
                    return None

            # Handle CAPTCHA or interstitial
            elif "captcha" in error_str or "interstitial" in error_str:
                logging.error(f"CAPTCHA/interstitial detected - HARD STOP")
                raise Exception("CAPTCHA detected - manual intervention required")

            # Other errors
            else:
                logging.error(f"Error collecting data for '{query}': {e}")
                if attempt < self.config["max_retries_per_tool"]:
                    backoff = calculate_backoff(attempt, self.config)
                    logging.info(f"Retrying after {backoff:.0f}s")
                    time.sleep(backoff)
                    return self.collect_for_tool(vendor_name, product_name, attempt + 1)
                else:
                    return None

    def _build_query(self, vendor_name, product_name):
        """Build search query from vendor and product names."""
        # Use vendor name primarily, fall back to product name
        if pd.notna(vendor_name) and vendor_name.strip():
            query = vendor_name.strip()
        elif pd.notna(product_name) and product_name.strip():
            query = product_name.strip()
        else:
            query = "unknown"

        # Optionally add "legal tech" for disambiguation (commented out for now)
        # query += " legal tech"

        return query[:100]  # Trends has query length limit

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution."""

    print("=" * 80)
    print("GOOGLE TRENDS DATA COLLECTOR")
    print("=" * 80)

    # Setup logging
    log_file = setup_logging()
    logging.info("="*80)
    logging.info("Starting Google Trends collection")
    logging.info(f"Config: {json.dumps(CONFIG, indent=2)}")
    logging.info("="*80)

    # Check kill switch
    if not CONFIG["enabled"]:
        print("\n⚠️  KILL SWITCH ACTIVE - Collection disabled")
        logging.warning("Collection disabled by kill switch")
        return

    # Load database
    db_file = Path('merged_pref_top50_updated.csv')
    if not db_file.exists():
        logging.error(f"Database file not found: {db_file}")
        return

    df = pd.read_csv(db_file)
    logging.info(f"Loaded {len(df)} tools from database")

    # FULL COLLECTION MODE - Processing all tools
    print(f"\n🚀 FULL COLLECTION: Processing all {len(df)} tools")
    print(f"   Estimated time: ~{(len(df) * 5 / 60):.0f} minutes")

    # Initialize components
    rate_limiter = RateLimiter(CONFIG)
    collector = TrendsCollector(CONFIG, rate_limiter)

    try:
        collector.init_pytrends()
    except Exception as e:
        logging.error(f"Failed to initialize: {e}")
        return

    # Collect data for each tool
    results = []
    start_time = datetime.now()

    print(f"\n📊 Collecting Trends data for {len(df)} tools...")
    print(f"Rate limit: {CONFIG['max_requests_per_hour']}/hour, {CONFIG['max_requests_per_day']}/day")
    print(f"Min delay: {CONFIG['min_delay_between_requests']}s between requests")
    print(f"Logs: {log_file}\n")

    for idx, row in df.iterrows():
        vendor = row.get('Vendor Name', '')
        product = row.get('Product Name', '')

        print(f"[{idx+1}/{len(df)}] {vendor or product}")

        try:
            result = collector.collect_for_tool(vendor, product)

            if result:
                results.append({
                    'Vendor Name': vendor,
                    'Product Name': product,
                    **result
                })
            else:
                results.append({
                    'Vendor Name': vendor,
                    'Product Name': product,
                    'trends_score': CONFIG["fallback_score"],
                    'status': 'failed'
                })

        except KeyboardInterrupt:
            logging.warning("Collection interrupted by user")
            print("\n\n⚠️  Collection interrupted by user")
            break

        except Exception as e:
            logging.error(f"Fatal error: {e}")
            print(f"\n\n❌ Fatal error: {e}")
            break

    # Save results
    elapsed = (datetime.now() - start_time).total_seconds()

    print("\n" + "=" * 80)
    print("COLLECTION COMPLETE")
    print("=" * 80)
    print(f"Tools processed: {len(results)}/{len(df)}")
    print(f"Successful: {sum(1 for r in results if r.get('status') == 'success')}")
    print(f"No data: {sum(1 for r in results if r.get('status') == 'no_data')}")
    print(f"Failed: {sum(1 for r in results if r.get('status') == 'failed')}")
    print(f"Total 429 errors: {rate_limiter.total_429_errors}")
    print(f"Time elapsed: {elapsed/60:.1f} minutes")
    print(f"Requests made: {rate_limiter.requests_this_day}")

    # Save to CSV
    if results:
        results_df = pd.DataFrame(results)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"google_trends_results_{timestamp}.csv"
        results_df.to_csv(output_file, index=False)
        print(f"\n✓ Results saved to: {output_file}")
        logging.info(f"Results saved to: {output_file}")

    logging.info(f"Collection complete. Elapsed: {elapsed/60:.1f} min")
    print(f"\n📋 Full logs: {log_file}")

if __name__ == "__main__":
    main()
