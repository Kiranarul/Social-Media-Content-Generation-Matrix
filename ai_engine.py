import pandas as pd
import google.generativeai as genai
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests
from collections import Counter
from enum import Enum

load_dotenv()

# API Configuration
API_KEY = os.getenv("GEMINI_API_KEY")
MONDAY_API_KEY = os.getenv("MONDAY_API_KEY")

if not API_KEY or API_KEY == "your_gemini_api_key_here":
    raise ValueError("GEMINI_API_KEY not configured")

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# Board IDs (Set these after creating boards)
BOARD_CONTENT_REQUEST = os.getenv("BOARD_CONTENT_REQUEST")
BOARD_CONTENT_OPTIONS = os.getenv("BOARD_CONTENT_OPTIONS")
BOARD_CONTENT_IDEA = os.getenv("BOARD_CONTENT_IDEA")
BOARD_TREND_HISTORY = os.getenv("BOARD_TREND_HISTORY")

# Excel file for reference data (stored in GitHub repo)
REFERENCE_DATA_FILE = "cybersecurity_content_pillars_matrix.xlsx"


class WorkflowStage(Enum):
    """Track which phase we're in"""
    RECOMMEND = "recommend"
    GENERATE_OPTIONS = "generate_options"
    FINALIZE = "finalize"


class MondayAPI:
    """Helper class for Monday.com API operations"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.url = "https://api.monday.com/v2"
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
            "API-Version": "2024-01"
        }
    
    def query(self, graphql_query, variables=None):
        """Execute GraphQL query"""
        response = requests.post(
            self.url,
            json={"query": graphql_query, "variables": variables or {}},
            headers=self.headers
        )
        response.raise_for_status()
        result = response.json()
        
        if "errors" in result:
            raise Exception(f"Monday API Error: {result['errors']}")
        
        return result
    
    def get_board_items(self, board_id, limit=100):
        """Fetch all items from a board"""
        query = """
        query ($board_id: ID!, $limit: Int!) {
            boards(ids: [$board_id]) {
                items(limit: $limit) {
                    id
                    name
                    column_values {
                        id
                        text
                        value
                    }
                }
            }
        }
        """
        result = self.query(query, {"board_id": board_id, "limit": limit})
        items = result["data"]["boards"][0]["items"]
        
        # Parse column values into dict
        parsed_items = []
        for item in items:
            parsed = {"id": item["id"], "name": item["name"]}
            for col in item["column_values"]:
                parsed[col["id"]] = col["text"] or col["value"]
            parsed_items.append(parsed)
        
        return parsed_items
    
    def create_item(self, board_id, item_name, column_values=None):
        """Create new item with column values"""
        query = """
        mutation ($board_id: ID!, $item_name: String!, $column_values: JSON) {
            create_item(board_id: $board_id, item_name: $item_name, column_values: $column_values) {
                id
            }
        }
        """
        result = self.query(query, {
            "board_id": board_id,
            "item_name": item_name,
            "column_values": column_values or "{}"
        })
        return result["data"]["create_item"]["id"]
    
    def update_column_value(self, item_id, column_id, value):
        """Update a specific column value"""
        query = """
        mutation ($item_id: ID!, $column_id: String!, $value: JSON!) {
            change_column_value(item_id: $item_id, column_id: $column_id, value: $value) {
                id
            }
        }
        """
        result = self.query(query, {
            "item_id": item_id,
            "column_id": column_id,
            "value": json.dumps(value)
        })
        return result["data"]["change_column_value"]["id"]
    
    def update_status(self, item_id, column_id, status_label):
        """Update status dropdown column"""
        return self.update_column_value(item_id, column_id, {"label": status_label})


class ContentStrategyAI:
    """AI-powered content strategist"""
    
    def __init__(self, monday_api):
        self.monday = monday_api
        self.history = self._load_history()
        self.reference_data = self._load_reference_data()
    
    def _load_history(self):
        """Load posting history from Monday.com"""
        try:
            return self.monday.get_board_items(BOARD_TREND_HISTORY)
        except:
            return []
    
    def _load_reference_data(self):
        """Load Excel reference sheets"""
        if not os.path.exists(REFERENCE_DATA_FILE):
            return {}
        
        xls = pd.ExcelFile(REFERENCE_DATA_FILE)
        return {
            "pillars": pd.read_excel(xls, sheet_name="Pillars_Subpillars"),
            "angles": pd.read_excel(xls, sheet_name="Content_Angles"),
            "formats": pd.read_excel(xls, sheet_name="Content_Formats"),
            "trends": pd.read_excel(xls, sheet_name="Trend_Radar")
        }
    
    def analyze_patterns(self):
        """Analyze historical posting patterns"""
        if not self.history:
            return {"message": "No history available"}
        
        platforms = [item.get("Platform", "") for item in self.history if item.get("Platform")]
        formats = [item.get("Format", "") for item in self.history if item.get("Format")]
        pillars = [item.get("Pillar", "") for item in self.history if item.get("Pillar")]
        
        return {
            "platform_distribution": Counter(platforms),
            "format_distribution": Counter(formats),
            "pillar_distribution": Counter(pillars),
            "total_posts": len(self.history)
        }
    
    def recommend_next_post(self):
        """Generate next best post recommendation"""
        patterns = self.analyze_patterns()
        
        # Define all options
        all_platforms = ["LinkedIn", "Instagram", "Twitter", "Facebook"]
        all_formats = ["Post", "Carousel", "Reel", "Video", "Poll", "Story"]
        
        # Get most used
        most_used_platform = patterns["platform_distribution"].most_common(1)[0][0] if patterns["platform_distribution"] else None
        most_used_format = patterns["format_distribution"].most_common(1)[0][0] if patterns["format_distribution"] else None
        
        # Recommend something different (rotation strategy)
        unused_platforms = [p for p in all_platforms if p != most_used_platform]
        unused_formats = [f for f in all_formats if f != most_used_format]
        
        recommended_platform = unused_platforms[0] if unused_platforms else all_platforms[0]
        recommended_format = unused_formats[0] if unused_formats else all_formats[0]
        
        # Get pillar gap
        used_pillars = list(patterns["pillar_distribution"].keys())
        all_pillars = self.reference_data["pillars"]["Pillar"].unique().tolist() if "Pillar" in self.reference_data["pillars"].columns else []
        gap_pillars = [p for p in all_pillars if p not in used_pillars]
        
        recommended_pillar = gap_pillars[0] if gap_pillars else all_pillars[0] if all_pillars else "General"
        
        # Generate reasoning
        reasons = []
        if patterns["platform_distribution"].get(recommended_platform, 0) == 0:
            reasons.append(f"You've never posted on {recommended_platform}")
        elif patterns["platform_distribution"].get(recommended_platform, 0) < 3:
            reasons.append(f"You've only posted {patterns['platform_distribution'][recommended_platform]} times on {recommended_platform}")
        
        if recommended_format not in patterns["format_distribution"]:
            reasons.append(f"You haven't tried {recommended_format} format yet")
        
        return {
            "platform": recommended_platform,
            "format": recommended_format,
            "pillar": recommended_pillar,
            "reasoning": " | ".join(reasons) if reasons else "Balanced content mix",
            "confidence_score": min(95, 70 + len(self.history))  # More history = more confidence
        }


def generate_10_topics(platform, format_type, pillar):
    """Generate 10 content topic options"""
    print(f"Generating 10 topics for {platform} {format_type} about {pillar}...")
    
    # Load context from reference data
    context_str = ""
    if os.path.exists(REFERENCE_DATA_FILE):
        xls = pd.ExcelFile(REFERENCE_DATA_FILE)
        if "Pillars_Subpillars" in xls.sheet_names:
            df_pillars = pd.read_excel(xls, sheet_name="Pillars_Subpillars")
            context_str += "PILLARS:\n" + df_pillars.to_json(orient='records')[:3000] + "\n\n"
        if "Content_Angles" in xls.sheet_names:
            df_angles = pd.read_excel(xls, sheet_name="Content_Angles")
            context_str += "ANGLES:\n" + df_angles.to_json(orient='records')[:3000] + "\n\n"
        if "Content_Formats" in xls.sheet_names:
            df_formats = pd.read_excel(xls, sheet_name="Content_Formats")
            context_str += "FORMATS:\n" + df_formats.to_json(orient='records')[:3000] + "\n\n"
    
    prompt = f"""
You are an elite content strategist for Infinitesol (cybersecurity company).

Context:
- Platform: {platform}
- Format: {format_type}
- Topic Pillar: {pillar}

Reference Data:
{context_str}

Generate EXACTLY 10 unique, high-impact content topics.

For each topic:
1. Catchy title (specific, actionable)
2. Brief description (2-3 sentences)
3. Map to sub-pillar from reference data
4. Map to content angle from reference data
5. Map to trend topic from reference data
6. Score: trend_score (1-10), credibility_score (1-10), virality_score (1-10)
7. Mark top 3 picks with is_top_3=true

Output STRICT JSON array matching this schema:
[
  {{
    "id": 1,
    "title": "string",
    "description": "string",
    "pillar": "string",
    "sub_pillar": "string",
    "content_angle": "string",
    "trend_topic": "string",
    "trend_score": 8,
    "credibility_score": 9,
    "virality_score": 7,
    "is_top_3": true
  }}
]

RAW JSON ONLY. No markdown.
"""
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Clean markdown
        if text.startswith("```json"):
            text = text[7:-3].strip()
        elif text.startswith("```"):
            text = text[3:-3].strip()
        
        topics = json.loads(text)
        print(f"✅ Generated {len(topics)} topics")
        return topics
    
    except Exception as e:
        print(f"❌ Error generating topics: {e}")
        return None


def generate_full_content(topic):
    """Generate complete content payload"""
    print(f"Generating full content for: {topic['title']}")
    
    prompt = f"""
You are writing a masterclass content post for Infinitesol.

Blueprint:
- Platform: {topic['platform']}
- Format: {topic['format']}
- Pillar: {topic['pillar']} ({topic['sub_pillar']})
- Angle: {topic['content_angle']}
- Trend: {topic['trend_topic']}
- Title: {topic['title']}
- Context: {topic['description']}

Requirements:
1. content: Full post text (format for platform - e.g., carousel slides, video script, etc.)
2. hooks: 5 alternative hooks (newline separated)
3. keywords: SEO keywords (comma separated)
4. competitor_insights: How legacy MSSPs fail vs how Infinitesol solves
5. engagement_score: Integer 1-10

Output STRICT JSON matching this schema:
{{
  "content": "full post text here",
  "hooks": "Hook 1\\nHook 2\\nHook 3\\nHook 4\\nHook 5",
  "keywords": "keyword1, keyword2, keyword3",
  "competitor_insights": "analysis here",
  "engagement_score": 9
}}

RAW JSON ONLY. No markdown.
"""
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        if text.startswith("```json"):
            text = text[7:-3].strip()
        elif text.startswith("```"):
            text = text[3:-3].strip()
        
        payload = json.loads(text)
        print(f"✅ Generated full content payload")
        return payload
    
    except Exception as e:
        print(f"❌ Error generating content: {e}")
        return None


def run_recommendation_stage():
    """PHASE 1: Generate and post recommendation"""
    print("\n=== PHASE 1: AI Recommendation ===")
    
    monday = MondayAPI(MONDAY_API_KEY)
    strategist = ContentStrategyAI(monday)
    
    # Get recommendation
    recommendation = strategist.recommend_next_post()
    
    # Post to Content Request board
    item_id = monday.create_item(
        board_id=BOARD_CONTENT_REQUEST,
        item_name=f"🎯 AI Recommendation: {recommendation['pillar']}",
        column_values=json.dumps({
            "Platform": {"label": recommendation["platform"]},
            "Format": {"label": recommendation["format"]},
            "Topic_Pillar": recommendation["pillar"],
            "Reasoning": recommendation["reasoning"],
            "Confidence_Score": str(recommendation["confidence_score"]),
            "Status": {"label": "Pending Review"}
        })
    )
    
    print(f"✅ Recommendation posted to Monday.com (Item ID: {item_id})")
    print(f"   Platform: {recommendation['platform']}")
    print(f"   Format: {recommendation['format']}")
    print(f"   Pillar: {recommendation['pillar']}")
    print(f"   Why: {recommendation['reasoning']}")
    
    return item_id


def run_generation_stage(request_item_id, platform, format_type, pillar):
    """PHASE 2: Generate 10 topic options"""
    print("\n=== PHASE 2: Topic Generation ===")
    
    # Generate 10 topics
    topics = generate_10_topics(platform, format_type, pillar)
    
    if not topics:
        print("❌ Topic generation failed")
        return None
    
    monday = MondayAPI(MONDAY_API_KEY)
    
    # Post ALL 10 to Content Options board
    topic_ids = []
    for topic in topics:
        item_id = monday.create_item(
            board_id=BOARD_CONTENT_OPTIONS,
            item_name=topic["title"],
            column_values=json.dumps({
                "Description": topic["description"],
                "Platform": {"label": platform},
                "Format": {"label": format_type},
                "Pillar": {"label": pillar},
                "Sub_Pillar": topic.get("sub_pillar", ""),
                "Content_Angle": topic.get("content_angle", ""),
                "Trend_Topic": topic.get("trend_topic", ""),
                "Trend_Score": str(topic.get("trend_score", 0)),
                "Credibility_Score": str(topic.get("credibility_score", 0)),
                "Virality_Score": str(topic.get("virality_score", 0)),
                "Is_Top_3": "Yes" if topic.get("is_top_3") else "No",
                "Status": {"label": "Pending Selection"},
                "Parent_Request_ID": request_item_id
            })
        )
        topic_ids.append(item_id)
    
    print(f"✅ Posted {len(topics)} options to Monday.com")
    print(f"   Top 3 picks marked with Is_Top_3=Yes")
    
    # Update request status
    monday.update_status(request_item_id, "Status", "Topics Generated")
    
    return topic_ids


def run_finalization_stage(selected_topic_item_id):
    """PHASE 3: Generate full content"""
    print("\n=== PHASE 3: Content Finalization ===")
    
    monday = MondayAPI(MONDAY_API_KEY)
    
    # Get selected topic details
    items = monday.get_board_items(BOARD_CONTENT_OPTIONS)
    selected_item = next((item for item in items if str(item["id"]) == str(selected_topic_item_id)), None)
    
    if not selected_item:
        print("❌ Selected item not found")
        return
    
    # Reconstruct topic object
    topic = {
        "title": selected_item["name"],
        "platform": selected_item.get("Platform", ""),
        "format": selected_item.get("Format", ""),
        "pillar": selected_item.get("Pillar", ""),
        "sub_pillar": selected_item.get("Sub_Pillar", ""),
        "content_angle": selected_item.get("Content_Angle", ""),
        "trend_topic": selected_item.get("Trend_Topic", ""),
        "description": selected_item.get("Description", "")
    }
    
    # Generate full content
    payload = generate_full_content(topic)
    
    if not payload:
        print("❌ Content generation failed")
        return
    
    # Post to Content Idea Generator board (all 20 columns!)
    final_item_id = monday.create_item(
        board_id=BOARD_CONTENT_IDEA,
        item_name=topic["title"],
        column_values=json.dumps({
            "Pillar": {"label": topic["pillar"]},
            "Sub_Pillar": topic["sub_pillar"],
            "Angle_Category": "",  
            "Content_Angle": topic["content_angle"],
            "Format_Category": "",  
            "Content_Type": topic["format"],
            "Platform": topic["platform"],
            "Trend_Category": "",  
            "Trend_Topic": topic["trend_topic"],
            "Urgency": {"label": "High"},
            "Target_Audience": "US Mid-Market / Enterprise",
            "Intent": {"label": "Authority Building"},
            "Competitor": "",
            "Status": {"label": "Done"},
            "AI_Output": payload.get("content", "")[:2000], 
            "Hooks": payload.get("hooks", "")[:2000],
            "Keywords": payload.get("keywords", "")[:2000],
            "Competitor_Insights": payload.get("competitor_insights", "")[:2000],
            "Engagement_Score": str(payload.get("engagement_score", "0")),
            "Last_Updated": datetime.now().strftime("%Y-%m-%d")
        })
    )
    
    # Log to history
    monday.create_item(
        board_id=BOARD_TREND_HISTORY,
        item_name=topic["title"],
        column_values=json.dumps({
            "Date": datetime.now().strftime("%Y-%m-%d"),
            "Platform": {"label": topic["platform"]},
            "Format": {"label": topic["format"]},
            "Pillar": {"label": topic["pillar"]},
            "SubPillar": topic["sub_pillar"],
            "Trend": topic["trend_topic"],
            "Angle": topic["content_angle"],
            "Description": topic["description"][:2000],
            "TrendScore": selected_item.get("Trend_Score", "0"),
            "CredScore": selected_item.get("Credibility_Score", "0"),
            "ViralScore": selected_item.get("Virality_Score", "0")
        })
    )
    
    # Update statuses
    monday.update_status(selected_topic_item_id, "Status", "Generated")
    monday.update_status(final_item_id, "Status", "Ready to Publish")
    
    print(f"✅ Full content generated and posted!")
    print(f"   Final Item ID: {final_item_id}")
    print(f"   Content preview: {payload.get('content', '')[:200]}...")


def main():
    """Main entry point - called by GitHub Actions"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python ai_engine.py <stage> [args]")
        print("Stages:")
        print("  recommend")
        print("  generate <request_item_id> <platform> <format> <pillar>")
        print("  finalize <selected_topic_item_id>")
        sys.exit(1)
    
    stage = sys.argv[1]
    
    if stage == "recommend":
        run_recommendation_stage()
    
    elif stage == "generate":
        if len(sys.argv) < 6:
            print("❌ Missing arguments for generate stage")
            sys.exit(1)
        request_item_id = sys.argv[2]
        platform = sys.argv[3]
        format_type = sys.argv[4]
        pillar = sys.argv[5]
        run_generation_stage(request_item_id, platform, format_type, pillar)
    
    elif stage == "finalize":
        if len(sys.argv) < 3:
            print("❌ Missing argument for finalize stage")
            sys.exit(1)
        selected_item_id = sys.argv[2]
        run_finalization_stage(selected_item_id)
    
    else:
        print(f"❌ Unknown stage: {stage}")
        sys.exit(1)


if __name__ == "__main__":
    main()
