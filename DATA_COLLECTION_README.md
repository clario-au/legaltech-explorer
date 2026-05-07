# Legal Tech Tool Data Collection Pipeline

This pipeline helps collect structured data for legal tech tools to add to the database.

## Overview

The pipeline has 3 stages:

1. **Find Websites** - Locate official websites for each tool
2. **Extract Data** - Scrape websites and extract structured data using AI
3. **Review & Merge** - Validate data and merge into main database

## Important Notes

### Data Quality Principles

1. **Conservative Extraction**: Only include data explicitly stated on websites
2. **Skip Uncertain Fields**: Better to leave empty than include guesses
3. **High-Confidence Fields**: Security certifications (ISO, SOC 2, GDPR) ONLY if clearly mentioned
4. **Avoid Legal Tech Hub**: Do not use Legal Tech Hub as a data source
5. **Skip Unreliable Fields**:
   - Customer Reviews
   - Customer Feedback Rating
   - Vendor Contact Details (hard to extract accurately)

### Known Challenges

From previous data collection attempts:
- **Security Certifications**: Often not clearly listed on websites - be very conservative
- **Contact Details**: Difficult to extract in consistent format - skip this field
- **Pricing**: Many tools don't list pricing publicly
- **Regions Served**: Often vague or not specified

## Stage 1: Find Websites

### Option A: Automated Search (Recommended for bulk)

```bash
python find_websites_auto.py
```

This script:
- Uses DuckDuckGo search to find official websites
- Automatically filters out Legal Tech Hub results
- Suggests most likely official website
- Allows manual confirmation or override
- Saves results to `tool_websites.json`

**Usage:**
1. Choose how many tools to process
2. Select automatic or manual confirmation mode
3. Review suggestions and confirm or provide correct URLs
4. Results saved to `tool_websites.json`

**Auto Mode**:
- Faster but may need review
- Uses heuristics to select best match
- Review `tool_websites.json` after completion

**Manual Mode**:
- Slower but more accurate
- You confirm each website before saving

### Option B: Manual Entry

Edit `tool_websites.json` directly:

```json
{
  "Tool Name": "https://example.com",
  "Another Tool": "https://another-example.com"
}
```

## Stage 2: Extract Data

Once you have websites in `tool_websites.json`:

```bash
python extract_tool_data.py
```

This script:
- Loads websites from `tool_websites.json`
- Scrapes each website (respecting rate limits)
- Extracts structured data using OpenAI API
- Saves results to CSV and JSON

**Process:**
1. Script asks how many tools to process
2. For each tool:
   - Fetches website content
   - Removes navigation, scripts, styling
   - Sends to OpenAI for extraction
   - Formats data to match database schema
3. Saves results with timestamp

**Output Files:**
- `extracted_data_TIMESTAMP.csv` - Ready for database import
- `extracted_data_TIMESTAMP.json` - For detailed review

**Rate Limiting:**
- 2-second delay between requests
- Processes in batches to avoid overload
- Can resume if interrupted

## Stage 3: Review & Merge

### Manual Review

Before merging, review the extracted data:

```python
import pandas as pd

# Load extracted data
df = pd.read_csv('extracted_data_TIMESTAMP.csv')

# Check for common issues
print("Missing Vendor Names:", df['Vendor Name'].isna().sum())
print("Missing Descriptions:", df['Product Description'].isna().sum())
print("AI Powered distribution:", df['AI Powered'].value_counts())

# Review security certifications (should be conservative)
certs = df[df['ISO Certifications'] != '']['ISO Certifications'].value_counts()
print("ISO Certifications found:", certs)

# Check for suspiciously complete data (might be hallucinated)
complete_rows = df.notna().sum(axis=1)
print("Rows with >20 fields filled:", (complete_rows > 20).sum())
```

### Data Validation Checks

Check for these red flags:

1. **Too Complete**: If a row has almost all fields filled, review carefully - AI may be guessing
2. **Security Certs**: Verify any ISO/SOC 2/GDPR certifications by checking the website manually
3. **Pricing**: Check if pricing seems reasonable for tool type
4. **AI Powered**: Verify AI claims (should only be "Yes" if clearly mentioned)

### Merge with Database

```python
import pandas as pd

# Load existing database
existing = pd.read_csv('merged_pref_top50.csv')

# Load new data
new_data = pd.read_csv('extracted_data_TIMESTAMP.csv')

# Remove any duplicates (shouldn't be any if deduplication worked)
new_data = new_data[~new_data['Vendor Name'].isin(existing['Vendor Name'])]

# Merge
combined = pd.concat([existing, new_data], ignore_index=True)

# Save
combined.to_csv('merged_pref_top50_updated.csv', index=False)

print(f"Added {len(new_data)} new tools")
print(f"Total tools: {len(combined)}")
```

## Cost Estimation

### OpenAI API Costs (GPT-4o-mini)

Approximate costs per tool:
- Input: ~8,000 tokens (website content) = $0.0012
- Output: ~1,000 tokens (extracted data) = $0.0006
- **Total per tool: ~$0.002**

For 369 tools:
- **Estimated cost: ~$0.74 USD**

### Time Estimation

- Website search: ~10-30 seconds per tool (manual confirmation)
- Data extraction: ~5-10 seconds per tool
- **Total time for 369 tools**:
  - Automated: ~2-3 hours
  - With manual review: ~4-6 hours

## Tips for Best Results

### 1. Start Small

Process 10-20 tools first to test the pipeline:

```bash
python find_websites_auto.py
# Select "2" and enter "10"

python extract_tool_data.py
# Enter "10"
```

Review the results before processing all 369 tools.

### 2. Batch Processing

Process in batches of 50-100 to avoid:
- Long running processes
- API rate limits
- Losing progress if interrupted

### 3. Website Quality

Tools with better websites will have better extraction:
- Corporate sites with clear product pages: Excellent
- Simple landing pages: Good
- Marketing-heavy sites: Fair
- No website / redirect: Poor

### 4. Manual Verification

Always manually verify these fields:
- ISO Certifications
- Security & Compliance Certifications
- Pricing ranges
- HQ locations

## Troubleshooting

### "No websites found"

- Try manual mode in `find_websites_auto.py`
- Search Google manually and add to `tool_websites.json`
- Some tools may not have websites anymore

### "Failed to scrape"

Common reasons:
- Website blocks automated requests
- Website requires JavaScript (use manual data entry)
- Website is down/moved
- Anti-bot protection

Solution: Skip these tools or manually extract data

### "Extraction failed"

- Check OpenAI API key in `.env`
- Check API quota/credits
- Website content may be too complex/unstructured

### "Data looks wrong"

- AI may hallucinate for sparse websites
- Review and manually correct
- Consider marking field as empty if unsure

## Example Workflow

### Complete workflow for 20 tools:

```bash
# Step 1: Find websites
python find_websites_auto.py
# Choose: Process first 20 tools
# Choose: Manual confirmation mode
# Review and confirm each website

# Step 2: Extract data
python extract_tool_data.py
# Enter: 20

# Step 3: Review results
import pandas as pd
df = pd.read_csv('extracted_data_20241219_143022.csv')
df.head()

# Step 4: Manual spot-checks
# - Open 3-5 random tool websites
# - Compare extracted data with website
# - Check security certifications

# Step 5: If quality looks good, process more
# Otherwise, adjust prompts in extract_tool_data.py
```

## Files Generated

| File | Purpose |
|------|---------|
| `tool_websites.json` | Mapping of tool names to website URLs |
| `extracted_data_TIMESTAMP.csv` | Extracted data ready for database import |
| `extracted_data_TIMESTAMP.json` | Full extraction results with metadata |
| `extracted_data_partial.json` | Resumption point if process interrupted |

## Next Steps After Data Collection

1. Review extracted data quality
2. Manually verify high-confidence fields
3. Fill in missing critical fields manually
4. Merge with `merged_pref_top50.csv`
5. Update database UI to use new CSV
6. Test search functionality with new tools
7. Deploy updated database to Render

## Quality Checklist

Before merging new data:

- [ ] All vendor names present and correct
- [ ] Product descriptions make sense
- [ ] No obvious hallucinations
- [ ] Security certifications verified for 5-10 random tools
- [ ] AI Powered field only "Yes" when clearly AI-based
- [ ] Pricing ranges seem reasonable
- [ ] Legal functionality categories are correct
- [ ] No duplicate entries
- [ ] Website URLs all valid and correct

---

**Remember**: Quality over quantity. It's better to have 200 high-quality tool entries than 369 entries with uncertain data.
