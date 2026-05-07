# Popularity Scoring Options for Legal Tech Tools

You want to sort tools by popularity instead of alphabetically. Here are your options:

---

## Option 1: Simple Heuristic Scoring (FREE - Ready Now)

The script `add_popularity_metrics.py` uses:
- **Maturity level** (Advanced tools = more established)
- **AI-powered** (Yes = trending/popular)
- **Website quality** (HTTPS, response time, accessibility)
- **Data completeness** (more filled fields = more info available = likely more known)

**Pros:**
- Free
- Works immediately
- No API keys needed

**Cons:**
- Not based on actual traffic/popularity
- Heuristic-based estimation

**Usage:**
```bash
python add_popularity_metrics.py
```

---

## Option 2: Google Trends Data (FREE)

Use `pytrends` library to get relative search interest.

**What it measures:** How often people search for each tool on Google

**Installation:**
```bash
pip install pytrends
```

**Pros:**
- Free
- Real search data
- Good indicator of public interest

**Cons:**
- Rate limited (need delays between requests)
- Relative scores, not absolute numbers
- Takes time for 129 tools (~15-20 minutes)

---

## Option 3: SimilarWeb API (PAID - Most Accurate)

Get actual website traffic estimates.

**What it measures:** Monthly visitors, traffic sources, engagement

**Cost:** $149-$499/month for API access

**Pros:**
- Most accurate traffic data
- Professional-grade metrics
- Trusted by businesses

**Cons:**
- Expensive
- Requires paid API key

---

## Option 4: Tranco Ranking (FREE)

Research-oriented top sites ranking (replacement for Alexa).

**What it measures:** Global website ranking based on traffic

**Pros:**
- Free
- Updated daily
- Academic-backed

**Cons:**
- Only covers top 1M sites (many legal tech tools won't be ranked)
- Need to download large list file (50MB+)

**Usage:**
1. Download list from https://tranco-list.eu/
2. Match domains against the list

---

## Option 5: Combination Approach (RECOMMENDED)

Use multiple free sources and combine scores:

1. **Google Trends** (search interest) - 40% weight
2. **Website quality metrics** (HTTPS, speed, accessibility) - 20% weight
3. **Maturity/AI indicators** - 20% weight
4. **Data completeness** - 20% weight

**Time:** ~15-20 minutes for 129 tools
**Cost:** FREE

---

## Quick Recommendation

**If you want results now:** Use Option 1 (already created)

**If you want accurate data:** Use Option 5 (I can create this)

**If you have budget:** Use Option 3 (SimilarWeb)

---

## Implementation

Which option would you like me to implement?

I can create:
- **Option 5** (Combination with Google Trends) - Most balanced, FREE
- **Manual ranking** - You provide a list of "known popular tools" and I boost their scores
- **Custom formula** - Tell me what factors matter to you

Let me know your preference!
