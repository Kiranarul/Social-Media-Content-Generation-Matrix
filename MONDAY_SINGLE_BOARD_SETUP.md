# One-Board Setup Guide & Workflow Instructions

Use this master guide to create your **AI Content Factory** board. 

---

## Step 1: Create Board & 4 Specific Groups

1. In Monday.com, click "+ Add New" → "Board"
2. Name it: **"🚀 AI Content Factory"**
3. Click "+ Add Group" 4 times and rename them EXACTLY to this flow logic to avoid confusing automations:

### Group 1: "📥 Active Requests"
- Where you start new content requests and AI posts initial recommendations.

### Group 2: "💡 Topic Options"  
- When 10 topics are generated, the parent item is automatically moved here. 

### Group 3: "✅ Ready Content"
- Final approved content drops here as a fresh new item, with the massive markdown script saved securely in the Updates!

### Group 4: "📚 History"
- Move completed posts here to track past performance.

---

## Step 2: Initialize Core Columns

Add these exact columns to your board. Note: You don't have to display all of them in every Group level, but they must exist on the Board.

| Column Name | Type | Settings |
|-------------|------|----------|
| Platform | Dropdown | LinkedIn, Instagram, Twitter, Facebook |
| Format | Dropdown | Post, Carousel, Reel, Video, Poll, Story |
| Topic Pillar | Text | |
| Description | Long Text | |
| Trend | Text | |
| Status | Status | Set labels exactly as follows: `Ready to Generate`, `Topics Generated`, `Selecting Topic`, `Topic Selected`, `Content Generated`, `Ready to Publish`, `Done` |

---

## Step 3: Initialize Subitem Columns

Under any item, add a Subitem. Then add these columns to the Subitem layer so the AI can inject data:
* `Description` (Long Text)
* `Platform` (Dropdown)
* `Format` (Dropdown)
* `Sub Pillar` (Text)
* `Angle` (Text)
* `Trend` (Text)
* `Status` (Status) - Labels: `Pending Selection`, `Topic Selected`, `Content Generated`

> [!IMPORTANT]
> Change the default value of the Subitem **Status** column to **Pending Selection**. This prevents automations misfiring!

---

## Step 4: Create Critical Automations

### Automation A: Movement to Options
```
WHEN Status changes to "Topics Generated"
THEN Move item to "💡 Topic Options" group
```

### Automation B: Movement to History
```
WHEN Status changes to "Done"
THEN Move item to "📚 History" group
```

### Automation C: Webhook Phase 1 (Target Search)
```
WHEN Status changes to "Ready to Generate"
THEN Send webhook
     URL: https://api.github.com/repos/Kiranarul/Social-Media-Content-Generation-Matrix/dispatches
     Event: monday-start-generation
     Payload: {
       "request_item_id": "{{item.id}}",
       "platform": "{{Platform}}",
       "format": "{{Format}}",
       "pillar": "{{Topic Pillar}}"
     }
```

### Automation D: Webhook Phase 2 (Content Finalization)
```
WHEN Subitem Status changes to "Topic Selected"
THEN Send webhook
     URL: https://api.github.com/repos/Kiranarul/Social-Media-Content-Generation-Matrix/dispatches
     Event: monday-topic-selected
     Payload: {
       "selected_item_id": "{{item.id}}"
     }
```

> [!NOTE]
> *Because our upgraded Python backend uses Monday.com's native GraphQL recursively, you do NOT need to pass the parent item ID in the webhook! The AI finds everything automatically just using `item.id`.*

---

## Step 5: Extract Your Board ID

1. Open your "AI Content Factory" board
2. Look at URL: `https://app.monday.com/boards/1234567890`
3. Copy the number (e.g., `1234567890`)
4. Add to your GitHub Actions Secrets panel as `MASTER_BOARD_ID`.

---

## System Deployment Workflow

**You:**
1. Click "+ Add Item" in "📥 Active Requests" group.
2. Change Status → `Ready to Generate`

**System:**
- Sends Webhook `monday-start-generation`.
- GitHub action executes Phase 2. Natively generates 10 beautiful subitems under your request!
- System changes Parent Status to `Topics Generated`.
- *Automation A immediately moves the Parent to "💡 Topic Options".*

**You:**
- Review the 10 subitems!
- Select the ONE you want and change its status to `Topic Selected`

**System:**
- Sends Webhook `monday-topic-selected`.
- Github action executes Phase 3.
- Recursively matches subitem to parent, constructs incredible final post Markdown, and pushes it to a brand new item.
- System sets NEW item to `Ready to Publish`.
- System sets Subitem to `Content Generated`.
- System sets PARENT item to `Done`.
- *Automation B immediately moves the exhausted Parent directly into "📚 History" Archive!*
