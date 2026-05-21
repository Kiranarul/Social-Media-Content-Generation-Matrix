import os
import sys
import json
import time
import requests
from dotenv import load_dotenv
from google import genai

load_dotenv()

# Force UTF-8 stdout
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# API Config
API_KEY = os.getenv("GEMINI_API_KEY")
MONDAY_API_KEY = os.getenv("MONDAY_API_KEY")
MASTER_BOARD_ID = os.getenv("MASTER_BOARD_ID") or os.getenv("MONDAY_BOARD_ID")
MODEL_ID = "gemini-2.5-flash"

if not API_KEY or not MONDAY_API_KEY or not MASTER_BOARD_ID:
    print("❌ Error: Missing required credentials (GEMINI_API_KEY, MONDAY_API_KEY, MASTER_BOARD_ID)")
    sys.exit(1)

client = genai.Client(api_key=API_KEY)

# Group IDs from board metadata
HISTORY_GROUP = "group_mm1ws5h3"
READY_CONTENT_GROUP = "group_mm1wynes"

# Column IDs
PLATFORM_COL = "dropdown_mm1w7sd9"
FORMAT_COL = "dropdown_mm1w72b4"
PILLAR_COL = "text_mm1w3t2c"
DESC_COL = "long_text_mm1wzgth"
TREND_COL = "text_mm1wj52x"
STATUS_COL = "status"

# Subitem Column IDs
SUB_DESC_COL = "long_text_mm1wg3xz"
SUB_PLATFORM_COL = "dropdown_mm1wepd4"
SUB_FORMAT_COL = "dropdown_mm1wppt3"
SUB_PILLAR_COL = "text_mm1wxd4b"
SUB_ANGLE_COL = "text_mm1wv8e3"
SUB_TREND_COL = "text_mm1wesed"
SUB_STATUS_COL = "status"

class MondayAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.url = "https://api.monday.com/v2"
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
            "API-Version": "2024-01"
        }
    
    def query(self, graphql_query, variables=None):
        res = requests.post(self.url, json={"query": graphql_query, "variables": variables or {}}, headers=self.headers)
        res.raise_for_status()
        data = res.json()
        if "errors" in data: raise Exception(f"Monday API Error: {data['errors']}")
        return data
    
    def create_item(self, board_id, group_id, item_name, parent_id=None, column_values=None):
        if parent_id:
            q = """mutation($parent_id: ID!, $item_name: String!, $column_values: JSON) {
                create_subitem(parent_item_id: $parent_id, item_name: $item_name, column_values: $column_values) { id }
            }"""
            return self.query(q, {"parent_id": str(parent_id), "item_name": item_name, "column_values": column_values or "{}"})["data"]["create_subitem"]["id"]
        else:
            q = """mutation($board_id: ID!, $group_id: String!, $item_name: String!, $column_values: JSON) {
                create_item(board_id: $board_id, group_id: $group_id, item_name: $item_name, column_values: $column_values) { id }
            }"""
            return self.query(q, {"board_id": board_id, "group_id": group_id, "item_name": item_name, "column_values": column_values or "{}"})["data"]["create_item"]["id"]

    def post_update(self, item_id, body):
        if len(body) > 45000:
            body = body[:45000] + "<br><br><i>... (truncated for length)</i>"
        q = """mutation($item_id: ID!, $body: String!) {
            create_update(item_id: $item_id, body: $body) { id }
        }"""
        try:
            result = self.query(q, {"item_id": str(item_id), "body": body})
            return result["data"]["create_update"]["id"]
        except Exception as e:
            print(f"   ⚠️ Update posting failed, retrying plain-text fallback: {e}")
            import re
            plain = re.sub(r'<[^>]+>', ' ', body).strip()
            result = self.query(q, {"item_id": str(item_id), "body": plain[:10000]})
            return result["data"]["create_update"]["id"]

monday_api = MondayAPI(MONDAY_API_KEY)

# Define the content calendar
content_calendar = [
    {
        "day": "Monday",
        "title": "Top 5 Cybersecurity Mistakes Businesses Still Make in 2026",
        "platform": "Instagram",
        "format": "Reel",
        "description": "Instagram Reel (General Reach): Highlighting key security blunders businesses make today.",
        "prompt_guideline": "Generate a highly dynamic short-form video script. Include visual scene directions, on-screen text overlays, and an engaging spoken voiceover/dialogue. Keep the tempo fast-paced and suitable for an Instagram Reel/TikTok video. Ensure all double quotes inside JSON string values are escaped properly to avoid syntax errors."
    },
    {
        "day": "Monday",
        "title": "How SMBs Can Improve Security Posture Without Enterprise-Level Budgets",
        "platform": "LinkedIn",
        "format": "Newsletter",
        "description": "LinkedIn Newsletter/Article (Industry Targeted): Practical strategies to enhance SMB posture cost-effectively.",
        "prompt_guideline": "Write a structured long-form article. Use clear markdown headers (##), bullet points, and an engaging tone. Include a clear introduction, core actionable recommendations, and a strong professional conclusion."
    },
    {
        "day": "Tuesday",
        "title": "Why Businesses Need Regular Vulnerability Assessments",
        "platform": "LinkedIn",
        "format": "Carousel",
        "description": "LinkedIn Carousel (Service Promotion): Explaining the 'why' behind regular assessments.",
        "prompt_guideline": "Generate a slide-by-slide outline for a carousel (Slide 1 to 7). For each slide, specify: Slide Title, Visual Concept, and Slide Text. Ensure it has a strong progression from problem to solution."
    },
    {
        "day": "Tuesday",
        "title": "Signs Your Organization Needs a Security Audit",
        "platform": "Instagram",
        "format": "Carousel",
        "description": "Instagram Carousel (Service Promotion): Diagnostic signs that indicate an audit is overdue.",
        "prompt_guideline": "Generate a slide-by-slide outline (Slide 1 to 6). For each slide, detail: Slide Title, Visual/Graphic Concept, and Slide Copy. Make the language snappy and highly visual."
    },
    {
        "day": "Wednesday",
        "title": "Common VPN & Remote Access Vulnerabilities Companies Overlook",
        "platform": "Website",
        "format": "Article",  # Mapped to Article from Website Blog
        "description": "Website Blog (Industry Targeted): Analysis of overlooked entry points in remote access configurations.",
        "prompt_guideline": "Write a comprehensive blog article. Use HTML or Markdown headings to structure. Focus on technical clarity, detailing the vulnerabilities and providing clear remediation advice."
    },
    {
        "day": "Thursday",
        "title": "Remote Work Security Isn't Just About VPNs Anymore",
        "platform": "LinkedIn",
        "format": "Post",
        "description": "LinkedIn Post: Short-form insights from the Wednesday blog with a CTA to read the full article.",
        "prompt_guideline": "Write a punchy LinkedIn post. Open with an attention-grabbing hook, keep sentences short, use professional bullet points, and end with a strong Call to Action (CTA) pointing to the full Website Blog article."
    },
    {
        "day": "Friday",
        "title": "What worries you most about cybersecurity?",
        "platform": "Instagram",
        "format": "Poll",
        "description": "Instagram Poll (General Reach). Options: Data leaks, Ransomware, Employee mistakes, Weak passwords.",
        "prompt_guideline": "Generate a short caption introducing the poll question. Clearly list the 4 options: 1. Data leaks, 2. Ransomware, 3. Employee mistakes, 4. Weak passwords. Add a call to action asking users to vote and share their thoughts in the comments."
    },
    {
        "day": "Friday",
        "title": "What is the biggest cybersecurity challenge for businesses today?",
        "platform": "LinkedIn",
        "format": "Poll",
        "description": "LinkedIn Poll (General Reach). Options: Lack of awareness, Budget constraints, Outdated systems, Third-party risks.",
        "prompt_guideline": "Generate a professional LinkedIn caption introducing the poll. List the options: 1. Lack of awareness, 2. Budget constraints, 3. Outdated systems, 4. Third-party risks. Write a paragraph explaining the context of the poll and prompt the reader to comment with their thoughts."
    },
    {
        "day": "Friday",
        "title": "3 Red Flags That Your Business Network Is Vulnerable",
        "platform": "Instagram",
        "format": "Reel",
        "description": "Instagram Reel (Flexible: Service/Industry/General): Warning signs that network security is exposed.",
        "prompt_guideline": "Generate a short-form video script (scenes + voiceover script + on-screen text) highlighting 3 distinct signs of a vulnerable network. Focus on visual drama and clean voiceover hooks."
    },
    {
        "day": "Weekly",
        "title": "Cybersecurity is no longer optional infrastructure — it's business continuity.",
        "platform": "Twitter",
        "format": "Post",
        "description": "Twitter / X Post: Short, punchy thought leadership post.",
        "prompt_guideline": "Generate a short, viral-style text post for Twitter/X. Keep it within 280 characters, use strong spacing, and include relevant hashtags."
    },
    {
        "day": "Repurpose",
        "title": "Signs Your Organization Needs a Security Audit",
        "platform": "Facebook",
        "format": "Carousel",
        "description": "Facebook Repurpose: Tuesday Instagram carousel. Optimized for Facebook's user base.",
        "prompt_guideline": "Provide a slide-by-slide outline (Slide 1 to 6) optimized for Facebook. Focus on community engagement and corporate security culture."
    },
    {
        "day": "Repurpose",
        "title": "3 Red Flags That Your Business Network Is Vulnerable",
        "platform": "Facebook",
        "format": "Reel",
        "description": "Facebook Repurpose: Friday Instagram Reel. Optimized as a Facebook Reel/Video post.",
        "prompt_guideline": "Provide a video script (visual directions + speech) optimized specifically for Facebook Reels, emphasizing local/SMB network protection."
    },
    {
        "day": "Repurpose",
        "title": "Top 5 Cybersecurity Mistakes Businesses Still Make in 2026 (TikTok)",
        "platform": "Instagram",  # Mapped to Instagram since TikTok is not in the platform dropdown
        "description": "TikTok Repurpose: Monday Instagram Reel. Note: Platforms set to Instagram (since TikTok is not in Monday dropdown). Title edited for TikTok.",
        "format": "Reel",
        "prompt_guideline": "Create a high-energy TikTok video script (visuals + speech + overlay text) explaining the mistakes, starting with a 3-second hook designed to stop TikTok scrolling."
    }
]

def run_content_generation_with_retry(item, max_retries=5):
    print(f"\n--- Generating (with retry): {item['day']} - {item['platform']} {item['format']} ({item['title']}) ---")
    
    prompt = f"""
You are an elite content strategist for Infinitesol (a modern cybersecurity firm).
Determine a fitting Content Pillar, Sub-pillar, Content Angle, and Trend Topic for the following post topic:
Topic: "{item['title']}"
Platform: {item['platform']}
Format: {item['format']}
Description/Context: {item['description']}

Format-Specific Instruction: {item['prompt_guideline']}

Please generate:
1. content: The full formatted post or script as described in the instructions.
2. hooks: 5 alternative hooks/subject lines (newline separated)
3. keywords: SEO keywords (comma separated)
4. competitor_insights: How legacy MSSPs fail vs Infinitesol's approach
5. engagement_score: An integer between 1 and 10 representing engagement potential
6. pillar: The high-level content pillar (e.g. Threat Awareness, Compliance, Penetration Testing, Risk Mitigation, Thought Leadership)
7. sub_pillar: The specific sub-pillar
8. content_angle: The content angle used
9. trend_topic: The industry trend or context linked to it

Output a STRICT JSON response:
{{
  "pillar": "string",
  "sub_pillar": "string",
  "content_angle": "string",
  "trend_topic": "string",
  "content": "string",
  "hooks": "Hook 1\\n...",
  "keywords": "kw1, kw2",
  "competitor_insights": "analysis",
  "engagement_score": 9
}}
RAW JSON ONLY. No markdown wrappers. Ensure no unescaped control characters or unescaped quotes in the content JSON values.
"""
    
    backoff = 2
    for attempt in range(1, max_retries + 1):
        try:
            print(f"   Attempt {attempt}/{max_retries}...")
            response = client.models.generate_content(model=MODEL_ID, contents=prompt).text.strip()
            if response.startswith("```json"): response = response[7:-3].strip()
            elif response.startswith("```"): response = response[3:-3].strip()
            
            payload = json.loads(response)
            return payload
        except Exception as e:
            print(f"   ⚠️ Attempt {attempt} failed: {e}")
            if attempt == max_retries:
                return None
            time.sleep(backoff)
            backoff *= 2

def main():
    print(f"🚀 Starting Bulk Content Generation...")
    print(f"Total items to process: {len(content_calendar)}")
    
    for idx, item in enumerate(content_calendar):
        print(f"\n[{idx+1}/{len(content_calendar)}] Processing: {item['title']}")
        payload = run_content_generation_with_retry(item)
        if not payload:
            print("❌ Skipping item due to generation failure.")
            continue
        
        # 1. Create parent request item in HISTORY group (status Done)
        parent_name = f"📅 {item['day']} - {item['title']}"
        parent_col_values = {
            STATUS_COL: {"label": "Done"},
            PLATFORM_COL: {"labels": [item["platform"]]},
            FORMAT_COL: {"labels": [item["format"]]},
            PILLAR_COL: payload.get("pillar", "General"),
            DESC_COL: {"text": item["description"]},
            TREND_COL: payload.get("trend_topic", "")
        }
        
        try:
            parent_id = monday_api.create_item(
                MASTER_BOARD_ID,
                HISTORY_GROUP,
                parent_name,
                column_values=json.dumps(parent_col_values)
            )
            print(f"   ✅ Created Parent in History (ID: {parent_id})")
            
            # 2. Create subitem in history representing the selected topic
            sub_col_values = {
                SUB_STATUS_COL: {"label": "Content Generated"},
                SUB_PLATFORM_COL: {"labels": [item["platform"]]},
                SUB_FORMAT_COL: {"labels": [item["format"]]},
                SUB_PILLAR_COL: payload.get("sub_pillar", ""),
                SUB_ANGLE_COL: payload.get("content_angle", ""),
                SUB_TREND_COL: payload.get("trend_topic", ""),
                SUB_DESC_COL: {"text": item["description"]}
            }
            sub_id = monday_api.create_item(
                MASTER_BOARD_ID,
                "",
                item["title"],
                parent_id=parent_id,
                column_values=json.dumps(sub_col_values)
            )
            print(f"   ✅ Created Subitem in History (ID: {sub_id})")
            
            # 3. Create final item in READY CONTENT group (status Ready to Publish)
            final_col_values = {
                STATUS_COL: {"label": "Ready to Publish"},
                PLATFORM_COL: {"labels": [item["platform"]]},
                FORMAT_COL: {"labels": [item["format"]]},
                PILLAR_COL: payload.get("pillar", "General"),
                DESC_COL: {"text": item["description"]},
                TREND_COL: payload.get("trend_topic", "")
            }
            final_id = monday_api.create_item(
                MASTER_BOARD_ID,
                READY_CONTENT_GROUP,
                item["title"],
                column_values=json.dumps(final_col_values)
            )
            print(f"   ✅ Created Final Item in Ready Content (ID: {final_id})")
            
            # 4. Post update to final item
            content_body = (
                f"<h2>📝 FINAL GENERATED CONTENT</h2>"
                f"<br><b>Platform:</b> {item['platform']} | <b>Format:</b> {item['format']}"
                f"<br><b>Pillar:</b> {payload.get('pillar', 'N/A')} | <b>Sub-Pillar:</b> {payload.get('sub_pillar', 'N/A')}"
                f"<br><b>Trend:</b> {payload.get('trend_topic', 'N/A')}"
                f"<br><b>Content Angle:</b> {payload.get('content_angle', 'N/A')}"
                f"<br><br><h3>📄 Post Content</h3><br>{payload.get('content', '').replace('\n', '<br>')}"
                f"<br><br><h3>🎣 Alternative Hooks</h3><br>{payload.get('hooks', '').replace('\n', '<br>')}"
                f"<br><br><h3>🔑 Keywords</h3><br>{payload.get('keywords', '')}"
                f"<br><br><h3>⚔️ Competitor Insights</h3><br>{payload.get('competitor_insights', '').replace('\n', '<br>')}"
                f"<br><br><b>🎯 Engagement Score:</b> {payload.get('engagement_score', '?')}/10"
            )
            update_id = monday_api.post_update(final_id, content_body)
            print(f"   ✅ Posted final content update (Update ID: {update_id})")
            
        except Exception as e:
            print(f"❌ Error writing to Monday.com: {e}")
            
        time.sleep(1)

    print("\n🎉 Bulk Content Generation Completed Successfully!")

if __name__ == "__main__":
    main()
