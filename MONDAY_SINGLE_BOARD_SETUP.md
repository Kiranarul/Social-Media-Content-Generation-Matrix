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

## Step 4: Create Monday.com Automations (Only 2 Needed!)

> [!TIP]
> No webhooks required! GitHub Actions polls your board every 5 minutes automatically.

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

---

## Step 5: Configure GitHub Secrets

1. Open your "AI Content Factory" board
2. Look at URL: `https://app.monday.com/boards/1234567890`
3. Copy the number (e.g., `1234567890`)
4. Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions**
5. Add these 3 secrets:

| Secret Name | Value |
|-------------|-------|
| `MASTER_BOARD_ID` | Your board ID number |
| `MONDAY_API_KEY` | Your Monday.com API token |
| `GEMINI_API_KEY` | Your Google Gemini API key |

---

## How It Works (Poll-Based Architecture)

GitHub Actions runs every **5 minutes**, scanning your Monday board for status changes.

**You:**
1. Click "+ Add Item" in "📥 Active Requests" group.
2. Fill in **Platform**, **Format**, and optionally **Topic Pillar**.
3. Change Status → `Ready to Generate`

**System (within 5 minutes):**
- GitHub Actions detects the status change.
- Locks the item by setting status to `Selecting Topic`.
- Generates 10 topic subitems under your request.
- Sets parent status to `Topics Generated`.
- *Automation A moves the parent to "💡 Topic Options".*

**You:**
- Review the 10 subitems!
- Select the ONE you want and change its status to `Topic Selected`

**System (within 5 minutes):**
- GitHub Actions detects the subitem status change.
- Generates the full content post using AI.
- Creates a new item in "✅ Ready Content" with status `Ready to Publish`.
- Saves the full markdown post in the item's Updates section.
- Sets parent item to `Done`.
- *Automation B moves the parent to "📚 History".*

> [!NOTE]
> You can also trigger manually from GitHub: **Actions** tab → **Monday AI Content Factory** → **Run workflow** → Choose `poll` or `recommend`.

