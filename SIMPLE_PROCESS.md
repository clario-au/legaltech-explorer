# Simplified Data Collection Process

Since automated website finding is unreliable, here's the practical approach:

## Option 1: Process Tools with Known Websites Only

Use the tools we've already tested successfully:

```bash
python run_full_collection.py
# Select option 2 (Next 20 tools)
# Select 'n' for auto-finding (use cached only)
```

This will process the 4 tools we already have websites for:
- Smokeball
- CaseBlink
- PracticePanther
- Box

## Option 2: Add More Websites Manually (Recommended)

Create a simple list of tool websites in `tool_websites.json`:

```json
{
  "Smokeball": "https://www.smokeball.com",
  "CaseBlink": "https://www.caseblink.com",
  "PracticePanther": "https://www.practicepanther.com",
  "Box": "https://www.box.com",
  "Clio": "https://www.clio.com",
  "MyCase": "https://www.mycase.com"
}
```

Then run:
```bash
python run_full_collection.py
```

## Option 3: Quick Google Search Helper

For each Priority 1 tool, do a quick Google search:
1. Search "[tool name] legal tech" on Google
2. Find official website
3. Add to `tool_websites.json`

**Time estimate**: ~30 seconds per tool = 1 hour for 147 tools

## Recommended Workflow

**Step 1**: Start with the easiest 20-30 tools you can quickly find websites for

**Step 2**: Run collection on those:
```bash
python run_full_collection.py
```

**Step 3**: Review quality of extracted data

**Step 4**: If quality is good, continue adding more websites

**Step 5**: Merge results with main database

## Current Status

- **Tools in Priority 1**: 147
- **Websites found**: 4
- **Ready to extract**: 4 tools

**Next Action**: Add more websites to `tool_websites.json` manually, OR proceed with just the 4 we have to validate the full pipeline works end-to-end.
