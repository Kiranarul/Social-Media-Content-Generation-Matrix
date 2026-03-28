# Monday.com Board Setup Guide

Follow these steps to create the 4 required boards.

---

## Board 1: Content Request (Trigger Board)

**Purpose**: AI posts recommendations here for human approval

### Columns to Create:

| Column Name | Column Type | Settings |
|-------------|-------------|----------|
| Platform | Dropdown | Options: LinkedIn, Instagram, Twitter, Facebook |
| Format | Dropdown | Options: Post, Carousel, Reel, Video, Poll, Story |
| Topic Pillar | Text | |
| Reasoning | Long Text | |
| Confidence Score | Number | Min: 0, Max: 100 |
| Status | Status | Options: Pending Review, Approved, Overridden, Topics Generated |

### Automation to Create:

**Automation 1: Trigger Phase 1**
```
WHEN: Status changes to "Pending Review"
THEN: Send webhook to GitHub
     Webhook URL: https://api.github.com/repos/YOUR_USERNAME/YOUR_REPO/dispatches
     Event Type: monday-start-generation
     Payload: {
       "request_item_id": "{{item_id}}",
       "platform": "{{Platform}}",
       "format": "{{Format}}",
       "pillar": "{{Topic Pillar}}"
     }
```

---

## Board 2: Content Options (Selection Board)

**Purpose**: AI posts 10 topic options here, human selects top 3

### Columns to Create:

| Column Name | Column Type | Settings |
|-------------|-------------|----------|
| Description | Long Text | |
| Platform | Dropdown | Same as Board 1 |
| Format | Dropdown | Same as Board 1 |
| Pillar | Dropdown | Your pillar list |
| Sub Pillar | Text | |
| Content Angle | Text | |
| Trend Topic | Text | |
| Trend Score | Number | Min: 0, Max: 10 |
| Credibility Score | Number | Min: 0, Max: 10 |
| Virality Score | Number | Min: 0, Max: 10 |
| Is Top 3 | Dropdown | Options: Yes, No |
| Status | Status | Options: Pending Selection, Selected, Generated |
| Parent Request ID | Text | Stores link to original request |

### Automation to Create:

**Automation 2: Trigger Phase 3**
```
WHEN: Status changes to "Selected"
THEN: Send webhook to GitHub
     Event Type: monday-topic-selected
     Payload: {
       "selected_item_id": "{{item_id}}"
     }
```

---

## Board 3: Content Idea Generator (Final Output)

**Purpose**: Stores final approved content with all 20 columns

### Columns to Create (All 20 fields):

| Column Name | Column Type | Notes |
|-------------|-------------|-------|
| Pillar | Dropdown | |
| Sub Pillar | Text | |
| Angle Category | Dropdown | |
| Content Angle | Text | |
| Format Category | Dropdown | |
| Content Type | Dropdown | |
| Platform | Dropdown | |
| Trend Category | Dropdown | |
| Trend Topic | Text | |
| Urgency | Status | High/Medium/Low |
| Target Audience | Text | |
| Intent | Dropdown | |
| Competitor | Text | |
| Status | Status | To Do / In Progress / Done |
| AI Output | Long Text | The actual post content |
| Hooks | Long Text | 5 hook variations |
| Keywords | Text | SEO keywords |
| Competitor Insights | Long Text | Analysis |
| Engagement Score | Number | 1-10 |
| Last Updated | Date | Auto-update |

---

## Board 4: Trend Idea History (Archive)

**Purpose**: Historical tracking of all generated content

### Columns to Create:

| Column Name | Column Type |
|-------------|-------------|
| Date | Date |
| Title | Name (default column) |
| Platform | Dropdown |
| Format | Dropdown |
| Pillar | Dropdown |
| SubPillar | Text |
| Trend | Text |
| Angle | Text |
| Description | Long Text |
| TrendScore | Number |
| CredScore | Number |
| ViralScore | Number |

---

## Getting Board IDs

After creating each board:

1. Open the board in Monday.com
2. Look at the URL: `https://app.monday.com/boards/1234567890`
3. The number is your Board ID
4. Add to `.env` file or GitHub Secrets

---

## Setting Up GitHub Secrets

In GitHub Repository:

1. Go to Settings → Secrets and variables → Actions
2. Add these secrets:
   - `GEMINI_API_KEY`
   - `MONDAY_API_KEY`
   - `BOARD_CONTENT_REQUEST`
   - `BOARD_CONTENT_OPTIONS`
   - `BOARD_CONTENT_IDEA`
   - `BOARD_TREND_HISTORY`

---

## Testing the Workflow

1. **Test Phase 1**: Manually create item in Board 1, set status to "Pending Review"
   - Check GitHub Actions triggered
   - Check AI recommendation appears

2. **Test Phase 2**: Approve recommendation
   - Check 10 topics appear in Board 2
   - Verify Top 3 marked correctly

3. **Test Phase 3**: Select one topic (change status to "Selected")
   - Check full content appears in Board 3
   - Check history logged in Board 4
