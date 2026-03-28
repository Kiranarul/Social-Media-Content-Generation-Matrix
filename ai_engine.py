import pandas as pd
import google.generativeai as genai
import os
import json
from datetime import datetime
from dotenv import load_dotenv
import requests
from collections import Counter

load_dotenv()

# API Configuration
API_KEY = os.getenv("GEMINI_API_KEY")
MONDAY_API_KEY = os.getenv("MONDAY_API_KEY")

if not API_KEY or API_KEY == "your_gemini_api_key_here":
    print("WARNING: GEMINI_API_KEY not configured")

genai.configure(api_key=API_KEY)
# We default to gemini-2.5-flash for speed and context capabilities
model = genai.GenerativeModel("gemini-2.5-flash")

MASTER_BOARD_ID = os.getenv("MASTER_BOARD_ID")
REFERENCE_DATA_FILE = "cybersecurity_content_pillars_matrix.xlsx"

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
    
    def get_board_groups(self, board_id):
        return self.query("query($board_id: ID!) { boards(ids: [$board_id]) { groups { id title } } }", {"board_id": board_id})["data"]["boards"][0]["groups"]
    
    def get_group_items(self, board_id, group_id, limit=100):
        q = """
        query($board_id: ID!, $group_id: String!, $limit: Int!) {
            boards(ids: [$board_id]) {
                groups(ids: [$group_id]) {
                    items_page(limit: $limit) {
                        items { id name column_values { id text value } }
                    }
                }
            }
        }
        """
        items = self.query(q, {"board_id": board_id, "group_id": group_id, "limit": limit})["data"]["boards"][0]["groups"][0]["items_page"]["items"]
        parsed = []
        for i in items:
            p = {"id": i["id"], "name": i["name"]}
            for c in i["column_values"]: p[c["id"]] = c["text"] or c["value"]
            parsed.append(p)
        return parsed
    
    def create_item(self, board_id, group_id, item_name, parent_id=None, column_values=None):
        if parent_id:
            # Create subitem strictly with parent_item_id
            q = """mutation($parent_id: ID!, $item_name: String!, $column_values: JSON) {
                create_subitem(parent_item_id: $parent_id, item_name: $item_name, column_values: $column_values) { id }
            }"""
            return self.query(q, {"parent_id": str(parent_id), "item_name": item_name, "column_values": column_values or "{}"})["data"]["create_subitem"]["id"]
        else:
            q = """mutation($board_id: ID!, $group_id: String!, $item_name: String!, $column_values: JSON) {
                create_item(board_id: $board_id, group_id: $group_id, item_name: $item_name, column_values: $column_values) { id }
            }"""
            return self.query(q, {"board_id": board_id, "group_id": group_id, "item_name": item_name, "column_values": column_values or "{}"})["data"]["create_item"]["id"]
    
    def update_column_value(self, item_id, column_id, value):
        q = """mutation($item_id: ID!, $column_id: String!, $value: JSON!) {
            change_column_value(item_id: $item_id, column_id: $column_id, value: $value) { id }
        }"""
        return self.query(q, {"item_id": str(item_id), "column_id": column_id, "value": json.dumps(value)})["data"]["change_column_value"]["id"]
    
    def update_status(self, item_id, column_id, status_label):
        return self.update_column_value(item_id, column_id, {"label": status_label})

class ContentStrategyAI:
    def __init__(self, monday_api, board_id):
        self.monday = monday_api
        self.board_id = board_id
        self.groups = self._get_groups()
        self.history = self._load_history()
        self.ref = self._load_reference_data()
    
    def _get_groups(self):
        return self.monday.get_board_groups(self.board_id)
    
    def _load_history(self):
        hg = next((g for g in self.groups if "history" in g["title"].lower() or "archive" in g["title"].lower()), None)
        if not hg: return []
        try: return self.monday.get_group_items(self.board_id, hg["id"])
        except: return []
    
    def _load_reference_data(self):
        if not os.path.exists(REFERENCE_DATA_FILE): return {}
        xls = pd.ExcelFile(REFERENCE_DATA_FILE)
        return {
            "pillars": pd.read_excel(xls, sheet_name="Pillars_Subpillars") if "Pillars_Subpillars" in xls.sheet_names else pd.DataFrame(),
            "formats": pd.read_excel(xls, sheet_name="Content_Formats") if "Content_Formats" in xls.sheet_names else pd.DataFrame(),
        }
    
    def recommend_next_post(self):
        pl, fm, pi = [], [], []
        for i in self.history:
            pl.append(i.get("Platform", ""))
            fm.append(i.get("Format", ""))
            pi.append(i.get("Pillar", ""))
            
        pc, fc = Counter([p for p in pl if p]), Counter([f for f in fm if f])
        
        all_pl = ["LinkedIn", "Instagram", "Twitter", "Facebook"]
        all_fm = ["Post", "Carousel", "Reel", "Video", "Poll", "Story"]
        apil = self.ref.get("pillars", pd.DataFrame())
        all_pi = apil["Pillar"].unique().tolist() if not apil.empty and "Pillar" in apil.columns else []
        
        m_pl = pc.most_common(1)[0][0] if pc else None
        m_fm = fc.most_common(1)[0][0] if fc else None
        
        r_pl = next((p for p in all_pl if p != m_pl), all_pl[0])
        r_fm = next((f for f in all_fm if f != m_fm), all_fm[0])
        r_pi = next((p for p in all_pi if p not in pi), all_pi[0] if all_pi else "General")
        
        rs = []
        if pc.get(r_pl, 0) == 0: rs.append(f"Never posted on {r_pl}")
        if pc.get(r_pl, 0) < 3: rs.append(f"Only {pc.get(r_pl, 0)} posts on {r_pl}")
        if r_fm not in fc: rs.append(f"Haven't tried {r_fm} recently")
        
        return {
            "platform": r_pl, "format": r_fm, "pillar": r_pi,
            "reasoning": " | ".join(rs) if rs else "Balanced mix assigned automatically.",
            "confidence_score": min(95, 70 + len(self.history))
        }

def generate_10_topics(platform, format_type, pillar):
    print(f"Generating 10 topics for {platform} {format_type} about {pillar}...")
    ctx = ""
    if os.path.exists(REFERENCE_DATA_FILE):
        xls = pd.ExcelFile(REFERENCE_DATA_FILE)
        if "Pillars_Subpillars" in xls.sheet_names: ctx += "PILLARS:\n" + pd.read_excel(xls, sheet_name="Pillars_Subpillars").to_json(orient='records')[:3000] + "\n\n"
        if "Content_Angles" in xls.sheet_names: ctx += "ANGLES:\n" + pd.read_excel(xls, sheet_name="Content_Angles").to_json(orient='records')[:3000] + "\n\n"
        if "Trend_Radar" in xls.sheet_names: ctx += "TRENDS:\n" + pd.read_excel(xls, sheet_name="Trend_Radar").to_json(orient='records')[:3000] + "\n\n"
    
    prompt = f"""
You are an elite content strategist for Infinitesol (cybersecurity).
Context: Platform: {platform} | Format: {format_type} | Pillar: {pillar}
Reference Data:\n{ctx}
Generate EXACTLY 10 unique content topics mapping this context seamlessly.
Scores: trend_score, credibility_score, virality_score (1-10). Mark exactly 3 with is_top_3=true.
Output STRICT JSON array:
[{{ "id": 1, "title": "string", "description": "string", "pillar": "string", "sub_pillar": "string", "content_angle": "string", "trend_topic": "string", "trend_score": 8, "credibility_score": 9, "virality_score": 7, "is_top_3": true }}]
RAW JSON ONLY.
"""
    try:
        req = model.generate_content(prompt).text.strip()
        if req.startswith("```json"): req = req[7:-3].strip()
        elif req.startswith("```"): req = req[3:-3].strip()
        return json.loads(req)
    except Exception as e:
        print(f"❌ Error generating topics: {e}")
        return None

def generate_full_content(topic):
    print(f"Generating full content for: {topic.get('title')}")
    prompt = f"""
Write a masterclass content post for Infinitesol.
Blueprint: Platform: {topic.get('platform')} | Format: {topic.get('format')} | Pillar: {topic.get('pillar')} ({topic.get('sub_pillar')})
Angle: {topic.get('content_angle')} | Trend: {topic.get('trend_topic')} | Title: {topic.get('title')} | Context: {topic.get('description')}

1. content: Full post text explicitly optimized for the platform.
2. hooks: 5 alternative hooks (newline separated)
3. keywords: SEO keywords (comma separated)
4. competitor_insights: How legacy MSSPs fail vs Infinitesol
5. engagement_score: Integer 1-10

Output STRICT JSON:
{{ "content": "text", "hooks": "Hook 1\\n...", "keywords": "kw1, kw2", "competitor_insights": "analysis", "engagement_score": 9 }}
RAW JSON ONLY.
"""
    try:
        req = model.generate_content(prompt).text.strip()
        if req.startswith("```json"): req = req[7:-3].strip()
        elif req.startswith("```"): req = req[3:-3].strip()
        return json.loads(req)
    except Exception as e:
        print(f"❌ Error generating payload: {e}")
        return None

def run_recommendation_stage():
    print("=== PHASE 1: AI Recommendation ===")
    monday = MondayAPI(MONDAY_API_KEY)
    groups = monday.get_board_groups(MASTER_BOARD_ID)
    rg = next((g for g in groups if "Request" in g["title"] or "Active" in g["title"]), groups[0])
    
    rec = ContentStrategyAI(monday, MASTER_BOARD_ID).recommend_next_post()
    item_id = monday.create_item(MASTER_BOARD_ID, rg["id"], f"🎯 AI Recommendation: {rec['pillar']}", column_values=json.dumps({
        "dropdown_mm1w7sd9": {"labels": [rec.get("platform")]},
        "dropdown_mm1w72b4": {"labels": [rec.get("format")]},
        "text_mm1w3t2c": rec.get("pillar", ""),
        "long_text_mm1wzgth": {"text": rec.get("reasoning", "")},
        "status": {"label": "Ready to Generate"}
    }))
    print(f"✅ Posted (Item ID: {item_id})")

def run_generation_stage(request_id, platform, format_type, pillar):
    print("=== PHASE 2: Topic Generation ===")
    topics = generate_10_topics(platform, format_type, pillar)
    if not topics: return
    
    monday = MondayAPI(MONDAY_API_KEY)
    for t in topics:
        monday.create_item(MASTER_BOARD_ID, "", t["title"], parent_id=request_id, column_values=json.dumps({
            "long_text_mm1wg3xz": {"text": t.get("description", "")},
            "dropdown_mm1wepd4": {"labels": [platform]},
            "dropdown_mm1wppt3": {"labels": [format_type]},
            "text_mm1wxd4b": t.get("sub_pillar", ""),
            "text_mm1wv8e3": t.get("content_angle", ""),
            "text_mm1wesed": t.get("trend_topic", ""),
            "status": {"label": "Pending Selection"},
        }))
    print(f"✅ Created {len(topics)} sub-items successfully!")
    monday.update_status(request_id, "status", "Topics Generated")

def run_finalization_stage(selected_id):
    print("=== PHASE 3: Content Finalization ===")
    monday = MondayAPI(MONDAY_API_KEY)
    groups = monday.get_board_groups(MASTER_BOARD_ID)
    cg = next((g for g in groups if "Ready" in g["title"] or "Content" in g["title"]), groups[2] if len(groups)>2 else groups[0])
    
    # FETCH SUBITEM AND PARENT ITEM CONTEXT NATIVELY TO EXTRACT PARENT'S PLATFORM AND FORMAT!
    q = """
    query ($item_id: ID!) {
        items (ids: [$item_id]) {
            name
            column_values { id text }
            parent_item {
                name
                column_values { id text }
            }
        }
    }
    """
    try:
        res = monday.query(q, {"item_id": selected_id})
        si = res["data"]["items"][0]
        pi = si.get("parent_item")
        
        topic = {"title": si["name"], "platform": "", "format": "", "pillar": "", "sub_pillar": "", "content_angle": "", "trend_topic": "", "description": ""}
        
        # Load from subitem columns
        for c in si["column_values"]:
            l = c["id"].lower()
            if "platform" in l: topic["platform"] = c["text"]
            elif "format" in l: topic["format"] = c["text"]
            elif "pillar" in l: topic["pillar"] = c["text"]
            elif "angle" in l or "text" in l: topic["content_angle"] = c["text"]
            elif "trend" in l or "text1" in l: topic["trend_topic"] = c["text"]
            elif "description" in l or "long_text" in l: topic["description"] = c["text"]
            
        # Overwrite missing platform/format from PARENT item specifically!
        if pi:
            for c in pi["column_values"]:
                l = c["id"].lower()
                if "platform" in l and not topic["platform"]: topic["platform"] = c["text"]
                if "format" in l and not topic["format"]: topic["format"] = c["text"]
                if "pillar" in l and not topic["pillar"]: topic["pillar"] = c["text"]
                
        payload = generate_full_content(topic)
        if not payload: return
        
        final_id = monday.create_item(MASTER_BOARD_ID, cg["id"], topic["title"], column_values=json.dumps({"status": {"label": "Ready to Publish"}}))
        monday.query("""mutation($item_id: ID!, $body: String!) { create_update (item_id: $item_id, body: $body) { id } }""", {
            "item_id": str(final_id),
            "body": f"<h2>FINAL GENERATED CONTENT</h2><br><b>Post:</b><br>{payload.get('content', '')}<br><br><b>Hooks:</b><br>{payload.get('hooks', '')}"
        })
        monday.update_status(selected_id, "status", "Topic Selected")
        if pi:
             monday.update_status(pi["id"], "status", "Done")
        print("✅ Content perfectly mapped to Monday!")
    except Exception as e:
        print(f"❌ Could not pull specific subitem from graph: {e}")

def main():
    import sys
    if len(sys.argv) < 2: sys.exit(1)
    st = sys.argv[1]
    if st == "recommend": run_recommendation_stage()
    elif st == "generate": run_generation_stage(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif st == "finalize": run_finalization_stage(sys.argv[2])

if __name__ == "__main__":
    main()
