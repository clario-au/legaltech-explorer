"""
Test different approaches to fix Google Trends 429 errors
"""

import time
from pytrends.request import TrendReq

# Method 1: Add custom headers to mimic browser
print("Testing with custom headers...")
try:
    pytrends = TrendReq(
        hl='en-US',
        tz=360,
        timeout=(10, 25),
        retries=2,
        backoff_factor=0.1,
        requests_args={
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
            }
        }
    )

    print("Building payload for 'Adobe'...")
    pytrends.build_payload(['Adobe'], timeframe='today 12-m')

    print("Getting interest over time...")
    result = pytrends.interest_over_time()

    if not result.empty:
        avg_score = result['Adobe'].mean()
        print(f"SUCCESS! Average score: {avg_score:.2f}")
        print(f"Data points: {len(result)}")
    else:
        print("No data returned (but no error!)")

except Exception as e:
    print(f"FAILED: {str(e)}")

# Wait before next test
print("\nWaiting 30 seconds before next test...")
time.sleep(30)

# Method 2: Try with different timeframe
print("\nTesting with 3-month timeframe...")
try:
    pytrends2 = TrendReq(
        hl='en-US',
        tz=360,
        timeout=(10, 25),
        requests_args={
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
            }
        }
    )

    pytrends2.build_payload(['Microsoft'], timeframe='today 3-m')
    result2 = pytrends2.interest_over_time()

    if not result2.empty:
        avg_score = result2['Microsoft'].mean()
        print(f"SUCCESS! Average score: {avg_score:.2f}")
    else:
        print("No data returned")

except Exception as e:
    print(f"FAILED: {str(e)}")
