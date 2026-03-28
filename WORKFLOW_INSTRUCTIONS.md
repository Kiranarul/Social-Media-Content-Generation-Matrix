# How to Use the AI Content System

## Quick Start

### Step 1: Trigger AI Recommendation
- Go to "Content Request" board in Monday.com
- Click "+ Add Item" (or use existing)
- Change **Status** to **"Pending Review"**
- Wait 30 seconds

### Step 2: Review AI Recommendation
- AI will auto-fill:
  - Platform (e.g., "Instagram")
  - Format (e.g., "Reel")
  - Topic Pillar (e.g., "Cloud Security")
  - Reasoning (why this was chosen)
  - Confidence Score (how sure AI is)

**Options:**
- ✅ **Accept**: Leave as-is, proceed to Step 3
- ✏️ **Override**: Edit Platform/Format/Pillar manually

### Step 3: Generate Topic Options
- Change **Status** to **"Approved"**
- Wait 30-60 seconds
- Go to "Content Options" board
- You'll see 10 AI-generated topics
- Top 3 are marked with **"Is Top 3 = Yes"**

### Step 4: Select Your Favorite
- Review all 10 topics
- Each shows:
  - Title & Description
  - Scores (Trend, Credibility, Virality)
  - Platform/Format/Pillar mapping
- Change **Status** to **"Selected"** on your favorite

### Step 5: Get Final Content
- Wait 20-30 seconds
- Go to "Content Idea Generator" board
- Find your topic title
- All columns filled:
  - ✅ Full post content (AI Output)
  - ✅ 5 hook variations
  - ✅ SEO keywords
  - ✅ Competitor insights
  - ✅ Engagement score

### Step 6: Use the Content
- Copy/paste into social media scheduler
- Or export from Monday.com
- Or share with team for review

---

## Weekly Workflow Example

**Monday Morning:**
1. Trigger AI recommendation
2. Approve platform/format
3. Generate 10 topics
4. Select best one
5. Get complete content

**Total Time: 2-3 minutes** ⚡

**Result:** Week's content done!

---

## Pro Tips

1. **Batch Generation**: Generate 3-5 pieces at once for the week
2. **Mix Platforms**: Let AI rotate through different platforms
3. **Try New Formats**: Accept AI suggestions for formats you haven't tried
4. **Review History**: Check "Trend History" board to see what worked before
5. **Override When Needed**: If AI suggests wrong platform, manually change it

---

## Troubleshooting

**Issue**: GitHub Actions not triggering
- Check Monday.com automation has correct webhook URL
- Verify GitHub token has `repo` permissions
- Check webhook payload in Monday.com activity log

**Issue**: AI taking too long
- Normal: 30-60 seconds per phase
- If >2 minutes, check Gemini API quota
- Check GitHub Actions logs for errors

**Issue**: Content not appearing
- Verify Board IDs in GitHub Secrets are correct
- Check Monday.com API key is valid
- Review GitHub Actions logs for error messages
