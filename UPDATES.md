# Recent Updates - Store Feedback System

## Summary of Changes

### 1. Branding Update - Tarsyer Red Owl Logo ✅

**What Changed:**
- Added new Tarsyer owl logo (`frontend/public/logo.svg`) in red color scheme
- Updated all primary colors from blue (#1a73e8) to red (#EF4444)
- Updated login screen gradient to red tones
- Logo now displays on both login page and reports page

**Files Modified:**
- `frontend/public/logo.svg` (NEW) - Tarsyer owl logo
- `frontend/src/index.css` - Changed color variables from blue to red
- `frontend/src/App.jsx` - Updated logo reference

**Visual Changes:**
- Primary color: Blue (#1a73e8) → Red (#EF4444)
- Primary dark: Blue (#1557b0) → Red (#DC2626)
- Login background: Blue gradient → Red gradient
- All buttons, headers, and accents now use red theme

---

### 2. Analytics & Reports Dashboard ✅

**What's New:**
A complete, separate analytics dashboard accessible at `/reports.html` with comprehensive data visualization and reporting capabilities.

**Key Features:**

#### a) Overview Statistics
- Total feedbacks count
- Active stores count
- Positive feedback count
- Negative feedback count

#### b) Visual Analytics
- **Daily Trend Chart**: Bar chart showing feedback submissions over last 7/15/30/60 days
- **Sentiment Analysis**: Tone distribution with visual breakdown (positive/negative/neutral)
- **Top 10 Products Discussed**: Bar chart of most mentioned products
- **Top 10 Issues Reported**: Bar chart of most common issues
- **Top 10 Action Items**: Bar chart of suggested actions
- **Feedbacks by Store**: Store-wise comparison of feedback volumes

#### c) Data Table
- Searchable table with all analyzed feedbacks
- Columns: Date, Store, Sentiment, Summary, Actions
- Click any row to see full details

#### d) Detailed View Modal
- Full transcription text
- Audio playback
- Complete AI analysis summary
- Sentiment score (0-100%)
- Tagged products, issues, and actions
- Organized and easy to read

#### e) Filters & Export
- Filter by store (dropdown)
- Filter by date range (7/15/30/60 days)
- Export to CSV button for Excel analysis

**Files Created:**
- `frontend/src/pages/Reports.jsx` - Main reports component
- `frontend/src/pages/Reports.css` - Reports page styling
- `frontend/src/main-reports.jsx` - Reports entry point
- `frontend/reports.html` - Reports HTML page

**Files Modified:**
- `frontend/vite.config.js` - Added multi-page build configuration
- `README.md` - Updated documentation with reports access info

---

### 3. Backend Improvements ✅

**What Changed:**
- Fixed MAX_TOKENS from 1024 to 2048 to prevent JSON truncation
- Backend already had comprehensive analytics API at `/api/v1/dashboard/stats`

**Files Modified:**
- `.env.example` - Updated MAX_TOKENS=2048

**Why This Matters:**
The previous 1024 token limit was causing the Qwen AI responses to be cut off mid-JSON, resulting in invalid analysis data. Increasing to 2048 tokens ensures complete JSON responses with all analysis fields (summary, tone, products, issues, actions, keywords).

---

## How to Access

### Development (Local)
```bash
# Store Staff PWA
http://localhost:3000/

# Analytics & Reports Dashboard
http://localhost:3000/reports.html
```

### Production
```bash
# Store Staff PWA
https://store-feedback.tarsyer.com/

# Analytics & Reports Dashboard
https://store-feedback.tarsyer.com/reports.html
```

---

## Deployment Instructions

### 1. Update .env File on Server

Make sure your production `.env` file has the updated MAX_TOKENS value:

```bash
# On your server
cd ~/tarsyer-store-feedback
nano .env
```

Update this line:
```
MAX_TOKENS=2048
```

### 2. Rebuild and Deploy

```bash
# Run the deployment script
./deploy.sh
```

This will:
- Install updated backend dependencies
- Rebuild frontend with new reports page
- Restart all PM2 services (API + workers)

### 3. Restart Analysis Worker

To apply the new MAX_TOKENS setting:
```bash
pm2 restart analysis-worker
```

### 4. Verify Build

Check that reports.html was built:
```bash
ls -la frontend/dist/reports.html
```

### 5. Nginx Configuration

The existing nginx config already serves all files from `frontend/dist/`, so `reports.html` will be automatically accessible at:
```
https://store-feedback.tarsyer.com/reports.html
```

No nginx changes needed!

---

## Testing Checklist

After deployment, verify:

- [ ] Main PWA loads at `/` with red branding and Tarsyer logo
- [ ] Reports page loads at `/reports.html`
- [ ] Reports page shows all statistics and charts
- [ ] Store filter dropdown works
- [ ] Date range filter works (7/15/30/60 days)
- [ ] CSV export downloads correctly
- [ ] Clicking feedback row opens detail modal
- [ ] Detail modal shows transcription, audio, and analysis
- [ ] All charts render correctly (bar charts, tone chart, trend chart)
- [ ] Analysis worker no longer shows JSON truncation errors
- [ ] New feedbacks get complete analysis (not cut off)

---

## Features Summary

### Reports Dashboard Provides:

1. **Which stores sent feedback on which date**
   - Feedbacks by Store bar chart
   - Feedback table with Date + Store columns
   - Filter by specific store

2. **Count of tone (positive/negative/neutral)**
   - Sentiment Analysis chart with percentages
   - Total counts in stat cards at top
   - Visual breakdown with colors

3. **Top products discussed**
   - Top 10 Products bar chart
   - Extracted from AI analysis of all feedbacks

4. **Top issues**
   - Top 10 Issues Reported bar chart
   - Aggregated across all analyzed feedbacks

5. **Top action items**
   - Top 10 Action Items bar chart
   - Suggested actions from AI analysis

6. **Additional insights**
   - Daily submission trends
   - Store-wise comparison
   - CSV export for custom analysis
   - Detailed drill-down for each feedback

---

## Color Scheme Reference

### Old (Blue)
- Primary: #1a73e8
- Primary Dark: #1557b0
- Login gradient: Blue to lighter blue

### New (Red)
- Primary: #EF4444 (Tarsyer Red)
- Primary Dark: #DC2626
- Login gradient: Red (#EF4444) to lighter red (#F87171)
- Logo: Red owl mascot

All other colors (success green, warning yellow, danger red, neutrals) remain the same.

---

## API Endpoints Used by Reports

The reports page consumes these existing API endpoints:

- `GET /api/v1/dashboard/stats?days={N}&store_code={CODE}` - Main statistics
- `GET /api/v1/stores` - List of stores with feedback counts
- `GET /api/v1/feedbacks?limit=50&status=completed&store_code={CODE}` - Feedback list

No new backend code was needed - the APIs were already implemented!

---

## File Structure

```
store-feedback/
├── frontend/
│   ├── public/
│   │   └── logo.svg                    # NEW - Tarsyer owl logo
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Reports.jsx             # NEW - Reports page component
│   │   │   └── Reports.css             # NEW - Reports styling
│   │   ├── main-reports.jsx            # NEW - Reports entry point
│   │   ├── index.css                   # MODIFIED - Red color scheme
│   │   └── App.jsx                     # MODIFIED - Logo update
│   ├── reports.html                    # NEW - Reports HTML page
│   └── vite.config.js                  # MODIFIED - Multi-page build
├── backend/
│   └── app/
│       └── main.py                     # (No changes - APIs existed)
├── .env.example                        # MODIFIED - MAX_TOKENS=2048
├── README.md                           # MODIFIED - Updated docs
└── UPDATES.md                          # NEW - This file
```

---

## Next Steps

After deploying, you can:

1. Share the reports URL with managers: `https://store-feedback.tarsyer.com/reports.html`
2. Bookmark the reports page for easy access
3. Use CSV export for deeper analysis in Excel/Google Sheets
4. Monitor the daily trends to see feedback patterns
5. Track which products and issues are most frequently mentioned
6. Compare feedback volume across different stores

The dashboard updates in real-time as new feedbacks are analyzed!
