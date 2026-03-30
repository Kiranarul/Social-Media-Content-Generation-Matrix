# 🚀 AI Content Factory

> **Fully autonomous AI-powered content generation pipeline for Infinitesol's cybersecurity social media presence.**

GitHub Actions polls your Monday.com board every 5 minutes, detects status changes, and uses Google Gemini AI to generate strategic content — all hands-free after your initial click.

---

## 📐 Architecture Overview

```
┌─────────────────────┐     every 5 min      ┌──────────────────────┐
│   Monday.com Board   │ ◄──── polls ──────── │   GitHub Actions      │
│   "AI Content        │                      │   (content_ai.yml)    │
│    Factory"          │ ────── reads ──────► │                        │
│                      │                      │   ai_engine.py poll    │
│  ┌─ Active Requests  │                      │     ├─ Phase 2: Topics │
│  ├─ Topic Options    │ ◄── writes items ─── │     └─ Phase 3: Final  │
│  ├─ Ready Content    │                      │                        │
│  └─ History          │                      │   Google Gemini AI     │
└─────────────────────┘                      └──────────────────────┘
```

**No webhooks. No middleware. No manual triggering needed.**

---

## 🎯 How It Works

### The 3-Phase Content Pipeline

| Phase | Trigger | What Happens | Result |
|-------|---------|-------------|--------|
| **1. Recommend** | Weekly schedule or manual | AI analyzes your posting history and suggests the optimal Platform + Format + Pillar | New item appears in "Active Requests" |
| **2. Generate Topics** | You set status → `Ready to Generate` | AI generates 10 unique topic options as subitems | 10 subitems appear under your request |
| **3. Finalize Content** | You set subitem status → `Topic Selected` | AI writes the full post with hooks, keywords, and competitor insights | New item in "Ready Content" with full markdown |

### Your Workflow (3 Clicks Total)

```
YOU                                          SYSTEM (automatic)
───                                          ──────────────────

1. Create item in "Active Requests"
   Set Platform, Format (optional Pillar)
   Status → "Ready to Generate"
                                             ⏳ Within 5 minutes...
                                             → Generates 10 topic subitems
                                             → Moves item to "Topic Options"

2. Review the 10 subitems
   Pick your favorite one
   Subitem Status → "Topic Selected"
                                             ⏳ Within 5 minutes...
                                             → Generates full post content
                                             → Creates item in "Ready Content"
                                             → Archives parent to "History"

3. Open the "Ready Content" item
   Click "Updates" to see the full post
   Copy & publish! 🚀
```

---

## 🛠️ Setup Guide

### Prerequisites
- A [Monday.com](https://monday.com) account
- A [GitHub](https://github.com) account
- A [Google AI Studio](https://aistudio.google.com/apikey) API key

### Step 1: Monday.com Board Structure

Your board needs **4 groups** (in this exact order):

| Group | Purpose |
|-------|---------|
| 📥 **Active Requests** | Where you create new content requests |
| 💡 **Topic Options** | Items move here after 10 topics are generated |
| ✅ **Ready Content** | Final AI-generated content lands here |
| 📚 **History** | Completed/archived posts |

### Step 2: Board Columns (Parent Items)

These columns must exist on the board:

| Column | Type | Settings |
|--------|------|----------|
| Platform | Dropdown | `LinkedIn`, `Instagram`, `Twitter`, `Facebook` |
| Format | Dropdown | `Post`, `Carousel`, `Reel`, `Video`, `Poll`, `Story` |
| Topic Pillar | Text | Free text |
| Description | Long Text | Free text |
| Trend | Text | Free text |
| Status | Status | See labels below |
| Person | People | (optional) |
| Date | Date | (optional) |

**Status Labels** (must match exactly):
- `Ready to Generate` — Triggers AI topic generation
- `Selecting Topic` — System lock (set automatically)
- `Topics Generated` — Triggers Monday automation to move to Topic Options
- `Topic Selected` — (not used on parent)
- `Content Generated` — (not used on parent)
- `Ready to Publish` — Final content is ready
- `Done` — Triggers Monday automation to move to History

### Step 3: Subitem Columns

When you expand any item's subitems, these columns must exist:

| Column | Type | Settings |
|--------|------|----------|
| Description | Long Text | AI fills this with topic description |
| Platform | Dropdown | `LinkedIn`, `Instagram`, `Twitter`, `Facebook` |
| Format | Dropdown | `Post`, `Carousel`, `Reel`, `Video`, `Poll`, `Story` |
| Sub_Pillar | Text | AI fills this |
| Angle | Text | AI fills this with content angle |
| Trend | Text | AI fills this with trend topic |
| Status | Status | `Pending Selection` (default), `Topic Selected`, `Content Generated` |

> ⚠️ **Important:** Set the default subitem Status to `Pending Selection` to prevent the system from accidentally processing new subitems.

### Step 4: Monday.com Automations (Only 2!)

No webhooks needed. Just set up these 2 simple automations:

**Automation A:**
```
WHEN Status changes to "Topics Generated"
THEN Move item to "💡 Topic Options" group
```

**Automation B:**
```
WHEN Status changes to "Done"
THEN Move item to "📚 History" group
```

### Step 5: GitHub Repository Secrets

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret Name | Where to Get It |
|-------------|----------------|
| `MASTER_BOARD_ID` | Your Monday board URL: `monday.com/boards/`**`1234567890`** |
| `MONDAY_API_KEY` | Monday.com → Profile → Admin → API |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) |

---

## 📋 What You Do vs What the System Does

### What YOU do manually in Monday.com:

| Action | When | Where |
|--------|------|-------|
| Create a new item | When you want new content | "Active Requests" group |
| Set **Platform** dropdown | On new items | e.g., LinkedIn |
| Set **Format** dropdown | On new items | e.g., Post, Carousel |
| Set **Topic Pillar** (optional) | On new items | e.g., "HIPAA Compliance" |
| Set **Status** → `Ready to Generate` | After filling in the item | Triggers topic generation |
| Review 10 subitems | After topics appear (~5min) | "Topic Options" group |
| Set subitem **Status** → `Topic Selected` | When you pick your favorite | Triggers content generation |
| Copy final content from Updates | When ready to publish | "Ready Content" group |

### What the SYSTEM does automatically:

| Action | Trigger |
|--------|---------|
| Scans board for status changes | Every 5 minutes (GitHub Actions) |
| Generates 10 AI topic subitems | Detects `Ready to Generate` |
| Fills in Description, Angle, Trend, Sub-Pillar on each subitem | During topic generation |
| Moves parent to "Topic Options" | Monday Automation A |
| Generates full post with hooks & keywords | Detects subitem `Topic Selected` |
| Creates final item in "Ready Content" | During content finalization |
| Saves full markdown in item's Updates section | During content finalization |
| Sets parent to "Done" | During content finalization |
| Moves parent to "History" | Monday Automation B |
| Suggests next Platform + Format + Pillar | Every Monday 9AM EST |

---

## 🚀 First Run: Getting Your First Entry

Your board is empty. Here's how to populate it:

### Option A: Let AI Recommend (Fully Automatic)
1. Go to GitHub → **Actions** tab
2. Click **"Monday AI Content Factory"** on the left
3. Click **"Run workflow"** → Select **`recommend`** → Click **"Run workflow"**
4. Wait ~1 minute
5. Check your Monday board → A new item will appear in "Active Requests" with Platform, Format, Topic Pillar, and Description already filled in by AI!

### Option B: Create Your Own Request (Manual)
1. In Monday.com, go to "📥 Active Requests"
2. Click **"+ Add Item"**
3. Name it anything (e.g., "My First Post")
4. Set **Platform** → LinkedIn
5. Set **Format** → Post
6. Set **Topic Pillar** → "Zero Trust Security" (or any cybersecurity topic)
7. Set **Status** → `Ready to Generate`
8. Wait ~5 minutes for GitHub Actions to pick it up

### Then Continue the Flow:
1. Once 10 subitems appear, review them in "💡 Topic Options"
2. Pick your favorite subitem → Set its Status → `Topic Selected`
3. Wait ~5 minutes
4. Check "✅ Ready Content" for your finished post!

---

## 🧠 The AI Recommendation Engine

The `recommend` command analyzes your **History** group to suggest what to post next:

- **Platform balancing:** If you've posted 10× on LinkedIn but 0× on Instagram, it suggests Instagram
- **Format diversity:** If you always post text Posts, it suggests trying a Carousel or Reel
- **Pillar coverage:** Cross-references your Excel matrix to find underused content pillars
- **Confidence scoring:** Higher score = more data to work with

The recommendation runs automatically every **Monday at 9AM EST**, or you can trigger it manually anytime from GitHub Actions.

---

## 📁 Project Files

| File | Purpose |
|------|---------|
| `ai_engine.py` | Core AI engine — all 3 phases + poll scanner |
| `content_ai.yml` | GitHub Actions workflow (polling + recommendations) |
| `cybersecurity_content_pillars_matrix.xlsx` | Reference data: pillars, sub-pillars, angles, trends |
| `MONDAY_SINGLE_BOARD_SETUP.md` | Detailed board setup instructions |
| `requirements.txt` | Python dependencies |
| `.env` | Local environment variables (never committed) |
| `.env.example` | Template for `.env` |

---

## 🔧 Local Development

```bash
# Clone the repo
git clone https://github.com/Kiranarul/Social-Media-Content-Generation-Matrix.git
cd Social-Media-Content-Generation-Matrix

# Create .env from template
cp .env.example .env
# Edit .env with your actual API keys

# Install dependencies
pip install -r requirements.txt

# Run commands locally
python ai_engine.py recommend    # AI suggests next post
python ai_engine.py poll         # Scan board for pending actions
python ai_engine.py generate <item_id> <platform> <format> <pillar>  # Manual topic generation
python ai_engine.py finalize <subitem_id>   # Manual content finalization
```

---

## ❓ FAQ

**Q: Do I need to fill in Topic Pillar and Description manually?**
No! If you run `recommend`, the AI fills everything in. If you create items manually, you only need to set Platform and Format — Topic Pillar defaults to "General" if left empty.

**Q: How often does the system check my board?**
Every 5 minutes via GitHub Actions scheduled workflow.

**Q: Will it process the same item twice?**
No. The system immediately sets a "lock" status (`Selecting Topic` or `Content Generated`) before processing, so the next poll cycle skips it.

**Q: Can I use a private GitHub repo?**
Yes! The polling architecture doesn't need any inbound connections. Your secrets are encrypted and never exposed.

**Q: What if no actions are pending?**
The poll job completes in ~5 seconds with "No pending actions found" — minimal GitHub Actions usage.

**Q: Can I change the polling frequency?**
Yes, edit the cron in `.github/workflows/content_ai.yml`. Examples:
- `*/5 * * * *` = every 5 minutes (current)
- `*/10 * * * *` = every 10 minutes
- `*/15 * * * *` = every 15 minutes (saves GitHub Actions minutes)

---

## 📄 License

Private — Infinitesol LLC
