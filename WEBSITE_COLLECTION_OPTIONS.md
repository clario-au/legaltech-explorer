# Website Collection - 3 Easy Options

You need to collect website URLs for the 147 Priority 1 tools. Here are your options from fastest to slowest:

---

## Option 1: BULK INPUT (Fastest - 10 minutes)

**Best if**: You can quickly find/paste a list of URLs

### Steps:

1. **Create `bulk_urls.txt`** with one URL per line:
   ```
   smokeball.com
   clio.com
   mycase.com
   practicepanther.com
   ```

2. **Run the bulk importer**:
   ```bash
   python bulk_website_input.py
   ```

   This auto-matches URLs to tool names!

3. **Extract data**:
   ```bash
   python run_quick_collection.py
   ```

**Time**: 10-15 minutes for 20-30 tools

---

## Option 2: ASSISTED INPUT (Medium - 30 minutes)

**Best if**: You want suggestions and help

### Steps:

1. **Run the assisted finder**:
   ```bash
   python assisted_website_finder.py
   ```

2. **For each tool**, it will:
   - Show suggested URL (e.g., "smokeball.com")
   - Let you press Enter to accept
   - Or type 'open' to Google search
   - Or type the correct URL
   - Saves progress every 5 tools

3. **Extract data** when done:
   ```bash
   python run_quick_collection.py
   ```

**Time**: 30-60 minutes for 50-100 tools

---

## Option 3: MANUAL EDIT (Slowest - 1 hour+)

**Best if**: You want full control

### Steps:

1. **Edit `tool_websites.json` directly**:
   ```json
   {
     "Smokeball": "https://www.smokeball.com",
     "Clio": "https://www.clio.com",
     "MyCase": "https://www.mycase.com"
   }
   ```

2. **Extract data**:
   ```bash
   python run_quick_collection.py
   ```

**Time**: 1-2 hours for 147 tools

---

## Quick Start Recommendation

**Start with 20 tools using Option 2**:

1. Run `python assisted_website_finder.py`
2. Press Enter when suggestions look right
3. Type 'open' to Google when unsure
4. After 20 tools, type 'quit'
5. Run `python run_quick_collection.py`
6. Review quality
7. Continue if good!

---

## Current Status

- **Priority 1 tools**: 147
- **Websites found**: 3 (Smokeball, CaseBlink, PracticePanther)
- **Tools processed**: 3
- **Current database**: 245 tools (242 + 3 new)

---

## Pro Tip: Use Google Sheets

If you have a list of tools in a spreadsheet:

1. Add a column for URLs
2. Use a formula like: `="https://www."&LOWER(SUBSTITUTE(A2," ",""))&".com"`
3. Copy the working URLs
4. Paste into `bulk_urls.txt`
5. Run `python bulk_website_input.py`

This can get you 50-100 URLs in 15 minutes!

---

## What Happens After Collection?

Once you have websites in `tool_websites.json`:

1. `python run_quick_collection.py` extracts all data (~$0.002 per tool)
2. Outputs `new_tools_TIMESTAMP.csv`
3. Auto-merges with `merged_pref_top50.csv`
4. Ready to use in your app!

---

## Summary

| Method | Time for 50 tools | Difficulty |
|--------|-------------------|------------|
| **Bulk Input** | 10-15 min | Easy |
| **Assisted** | 30-45 min | Very Easy |
| **Manual** | 60-90 min | Medium |

**Recommendation**: Try Assisted mode for 10 tools first to see if you like it!
