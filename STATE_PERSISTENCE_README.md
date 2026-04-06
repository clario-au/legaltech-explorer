# State Persistence Feature

## Overview

The Legal-Tech Explorer now includes automatic state persistence that saves your current session across page reloads and browser refreshes. This means you won't lose your filters, search results, or compare selections when the page refreshes.

## What Gets Saved

The application automatically saves the following to browser localStorage:

1. **Search State**
   - Whether you've performed a search
   - Your last search query (for AI searches)

2. **Active Filters**
   - All selected filter values across all categories
   - Region filters
   - Legal functionality filters
   - User segment filters
   - Maturity level filters
   - Deployment and pricing filters
   - And all other active filters

3. **Compare Selection**
   - Which tools you've added to the compare list (up to 5)

4. **Timestamp**
   - When the state was last saved

## How It Works

### Automatic Saving
The application automatically saves your state whenever:
- You apply or change any filters
- You add or remove tools from the compare list
- You perform an AI search

### Automatic Restoration
When you reload the page (F5, Live Server refresh, etc.):
1. The CSV data is loaded
2. The application checks for saved state in localStorage
3. If valid saved state exists, it automatically:
   - Hides the landing page
   - Restores all your filters
   - Restores your compare selections
   - Re-applies filters to show your previous results

### State Expiration
- Saved state automatically expires after **24 hours**
- Expired state is automatically deleted
- This prevents stale data from persisting indefinitely

## User Controls

### Clear State (Return to Landing)
Click the **Clario logo** or **"Legal-Tech Explorer"** title in the top bar to:
- Return to the landing page
- Clear all filters
- Clear compare selections
- Delete saved state from localStorage

### Manual State Reset
You can also manually clear the saved state by:
1. Opening browser DevTools (F12)
2. Going to the Console tab
3. Running: `localStorage.removeItem('legaltech_explorer_state')`
4. Reloading the page

## Technical Details

### Storage Location
State is stored in browser localStorage under the key: `legaltech_explorer_state`

### Storage Format
```javascript
{
  "hasSearched": true,
  "lastQuery": "contract management tools",
  "compare": ["vendor1|product1|url1|0", "vendor2|product2|url2|1"],
  "filters": {
    "Regions Served": ["Australia", "New Zealand"],
    "Legal Functionality": ["Contract Management"],
    "Pricing Model": ["Subscription"]
  },
  "timestamp": 1704067200000
}
```

### Browser Compatibility
Works in all modern browsers that support localStorage:
- Chrome
- Firefox
- Edge
- Safari
- Opera

### Privacy & Security
- State is stored **only in your browser** (localStorage)
- Nothing is sent to any server
- State is unique to your browser and device
- Clearing browser data will clear saved state

## Benefits

### For Development (Live Server)
- No more losing your work when Live Server refreshes the page
- Test different filter combinations without starting over
- Maintain compare selections across code changes

### For Production Use
- Seamless experience when navigating away and returning
- Preserve user's exploration state during browser refreshes
- Better user experience with consistent state

### For Testing
- Quickly return to specific filter configurations
- Test edge cases with complex filter combinations
- Maintain test scenarios across page reloads

## Troubleshooting

### State Not Restoring
If your state isn't being restored:

1. **Check if state is being saved**:
   ```javascript
   // In browser console
   console.log(localStorage.getItem('legaltech_explorer_state'));
   ```

2. **Verify state age**:
   - State older than 24 hours is automatically deleted

3. **Check for errors**:
   - Open browser DevTools Console
   - Look for warnings like "Failed to save state" or "Failed to restore state"

4. **Clear and retry**:
   ```javascript
   localStorage.removeItem('legaltech_explorer_state');
   location.reload();
   ```

### State Seems Incorrect
If the restored state doesn't match what you expect:

1. Click the logo to return to landing page (this clears state)
2. Perform your search/filters again
3. The new state will be saved correctly

### Storage Quota Issues
If you see errors about storage quota:
- localStorage has a limit (usually 5-10MB)
- Our state is very small (typically < 50KB)
- If you hit quota, clear other site data or use browser cleanup tools

## Implementation Details

### Key Functions

**`saveState()`**
- Called automatically when filters or compare changes
- Serializes current state to JSON
- Stores in localStorage

**`loadState()`**
- Retrieves state from localStorage
- Checks expiration (24 hours)
- Returns parsed state object or null

**`restoreState(state)`**
- Takes saved state object
- Restores filters using `setFilterValue()`
- Restores compare selections
- Hides landing page and shows results

### Integration Points
State is saved at:
- `applyFilters()` - line 1075
- `toggleCompare()` - line 1049

State is loaded at:
- `loadCSVFromURL()` - lines 1122-1125 (after CSV loads)

State is cleared at:
- Brand logo click handler - line 1213

## Future Enhancements

Potential future additions:
- Save scroll position
- Save selected tool details
- Save compare tab selection (Table vs AI)
- Export/import state as JSON
- Multiple saved states (bookmarks)
- Sync state across devices (requires backend)
