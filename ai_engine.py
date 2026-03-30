import pandas as pd
from google import genai
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

# Using the new google-genai SDK (replaces deprecated google-generativeai)
client = genai.Client(api_key=API_KEY)
MODEL_ID = "gemini-2.5-flash"

MASTER_BOARD_ID = os.getenv("MASTER_BOARD_ID") or os.getenv("MONDAY_BOARD_ID")
REFERENCE_DATA_FILE = "cybersecurity_content_pillars_matrix.xlsx"

if not MASTER_BOARD_ID:
    print("❌ FATAL: MASTER_BOARD_ID is not set!")
    print("   → Add it to GitHub Secrets: Settings → Secrets → Actions → New Repository Secret")
    print("   → Name: MASTER_BOARD_ID  Value: your Monday.com board ID (e.g. 18406005838)")
    import sys; sys.exit(1)

print(f"✅ Board ID loaded: {MASTER_BOARD_ID}")

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
    
    def update_column_value(self, item_id, column_id, value, board_id=None):
        bid = board_id or MASTER_BOARD_ID
        q = """mutation($board_id: ID!, $item_id: ID!, $column_id: String!, $value: JSON!) {
            change_column_value(board_id: $board_id, item_id: $item_id, column_id: $column_id, value: $value) { id }
        }"""
        return self.query(q, {"board_id": bid, "item_id": str(item_id), "column_id": column_id, "value": json.dumps(value)})["data"]["change_column_value"]["id"]
    
    def update_status(self, item_id, column_id, status_label, board_id=None):
        return self.update_column_value(item_id, column_id, {"label": status_label}, board_id=board_id)

    def post_update(self, item_id, body):
        """Post a comment/update on any item or subitem. Surfaces full errors."""
        # Monday limits update body to ~50,000 chars — truncate safely
        if len(body) > 45000:
            body = body[:45000] + "<br><br><i>... (truncated for length)</i>"
        q = """mutation($item_id: ID!, $body: String!) {
            create_update(item_id: $item_id, body: $body) { id }
        }"""
        try:
            result = self.query(q, {"item_id": str(item_id), "body": body})
            update_id = result["data"]["create_update"]["id"]
            print(f"   ✅ Posted update (ID: {update_id}) on item {item_id}")
            return update_id
        except Exception as e:
            print(f"   ❌ FAILED to post update on item {item_id}: {e}")
            # Retry with plain text stripped of HTML tags
            import re
            plain = re.sub(r'<[^>]+>', ' ', body).strip()
            try:
                result = self.query(q, {"item_id": str(item_id), "body": plain[:10000]})
                update_id = result["data"]["create_update"]["id"]
                print(f"   ✅ Posted plain-text fallback update (ID: {update_id}) on item {item_id}")
                return update_id
            except Exception as e2:
                print(f"   ❌ FINAL FAILURE posting update on item {item_id}: {e2}")
                return None

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
        """Load items from ALL groups to understand what's already been created/processed."""
        all_items = []
        for g in self.groups:
            try:
                items = self.monday.get_group_items(self.board_id, g["id"])
                all_items.extend(items)
            except:
                pass
        print(f"   📊 Recommendation engine loaded {len(all_items)} items across {len(self.groups)} groups")
        return all_items
    
    def _load_reference_data(self):
        if not os.path.exists(REFERENCE_DATA_FILE): return {}
        xls = pd.ExcelFile(REFERENCE_DATA_FILE)
        return {
            "pillars": pd.read_excel(xls, sheet_name="Pillars_Subpillars") if "Pillars_Subpillars" in xls.sheet_names else pd.DataFrame(),
            "formats": pd.read_excel(xls, sheet_name="Content_Formats") if "Content_Formats" in xls.sheet_names else pd.DataFrame(),
        }
    
    def recommend_next_post(self):
        # Column ID mapping (must match Monday board column IDs, NOT display names)
        PLATFORM_COL = "dropdown_mm1w7sd9"
        FORMAT_COL = "dropdown_mm1w72b4"
        PILLAR_COL = "text_mm1w3t2c"
        
        pl, fm, pi = [], [], []
        for i in self.history:
            p = i.get(PLATFORM_COL, "")
            f = i.get(FORMAT_COL, "")
            pil = i.get(PILLAR_COL, "")
            if p: pl.append(p)
            if f: fm.append(f)
            if pil: pi.append(pil)
        
        print(f"   📊 History analysis: {len(pl)} platforms, {len(fm)} formats, {len(pi)} pillars found")
        print(f"   📊 Platforms used: {Counter(pl)}")
        print(f"   📊 Formats used: {Counter(fm)}")
        print(f"   📊 Pillars used: {Counter(pi)}")
            
        pc, fc = Counter(pl), Counter(fm)
        
        all_pl = ["LinkedIn", "Instagram", "Twitter", "Facebook"]
        all_fm = ["Post", "Carousel", "Reel", "Video", "Poll", "Story"]
        apil = self.ref.get("pillars", pd.DataFrame())
        all_pi = apil["Pillar"].unique().tolist() if not apil.empty and "Pillar" in apil.columns else []
        
        # Pick LEAST used platform (or unused one first)
        unused_pl = [p for p in all_pl if p not in pc]
        if unused_pl:
            r_pl = unused_pl[0]
        else:
            r_pl = pc.most_common()[-1][0]  # least used
        
        # Pick LEAST used format
        unused_fm = [f for f in all_fm if f not in fc]
        if unused_fm:
            r_fm = unused_fm[0]
        else:
            r_fm = fc.most_common()[-1][0]  # least used
        
        # Pick unused pillar
        r_pi = next((p for p in all_pi if p not in pi), all_pi[0] if all_pi else "General")
        
        rs = []
        if pc.get(r_pl, 0) == 0: rs.append(f"Never posted on {r_pl}")
        else: rs.append(f"Only {pc.get(r_pl, 0)} posts on {r_pl}")
        if r_fm not in fc: rs.append(f"Haven't tried {r_fm} recently")
        if r_pi not in pi: rs.append(f"Pillar '{r_pi}' not yet covered")
        
        print(f"   🎯 Recommending: {r_pl} / {r_fm} / {r_pi}")
        
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
        req = client.models.generate_content(model=MODEL_ID, contents=prompt).text.strip()
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
        req = client.models.generate_content(model=MODEL_ID, contents=prompt).text.strip()
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
        "status": {"label": "Done"}  # Human must manually set 'Ready to Generate' to proceed
    }))
    print(f"✅ AI Recommendation posted (Item ID: {item_id}) — status set to Done. Change to 'Ready to Generate' to trigger topic generation.")

def run_generation_stage(request_id, platform, format_type, pillar):
    print("=== PHASE 2: Topic Generation ===")
    topics = generate_10_topics(platform, format_type, pillar)
    if not topics: return
    
    # Sort by composite score — highest first
    for t in topics:
        t["_score"] = t.get("trend_score", 0) + t.get("credibility_score", 0) + t.get("virality_score", 0)
    topics.sort(key=lambda x: x["_score"], reverse=True)
    top_score = topics[0]["_score"]
    
    for i, t in enumerate(topics):
        t["_rank"] = i + 1
        if i < 3:
            print(f"  ⭐ TOP {i+1}: {t['title']} (Score: {t['_score']}/30)")
    
    monday = MondayAPI(MONDAY_API_KEY)
    for i, t in enumerate(topics):
        rank = t["_rank"]
        
        # Clean title — NO prefix stars, ranking goes in comment only
        sub_id = monday.create_item(MASTER_BOARD_ID, "", t["title"], parent_id=request_id, column_values=json.dumps({
            "long_text_mm1wg3xz": {"text": t.get("description", "")},
            "dropdown_mm1wepd4": {"labels": [platform]},
            "dropdown_mm1wppt3": {"labels": [format_type]},
            "text_mm1wxd4b": t.get("sub_pillar", ""),
            "text_mm1wv8e3": t.get("content_angle", ""),
            "text_mm1wesed": t.get("trend_topic", ""),
            "status": {"label": "Pending Selection"},
        }))
        
        # Post score comment in Updates — use dedicated method with full error surfacing
        if rank == 1:
            rank_badge = "🥇 AI TOP PICK — RANK #1"
            why = (
                f"<br><br><b>💡 Why this is ranked #1:</b><br>"
                f"Highest overall score ({t['_score']}/30) across all 3 dimensions. "
                f"Trend: {t.get('trend_score')}/10 — currently hot in cybersecurity. "
                f"Credibility: {t.get('credibility_score')}/10 — Infinitesol has strong authority here. "
                f"Virality: {t.get('virality_score')}/10 — high sharing potential on {platform}."
            )
        elif rank == 2:
            rank_badge = "🥈 AI RECOMMENDED — RANK #2"
            why = (
                f"<br><br><b>💡 Why Rank #2:</b><br>"
                f"Score {t['_score']}/30 — {top_score - t['_score']} pt(s) behind #1. "
                f"Good pick if #1 feels too broad."
            )
        elif rank == 3:
            rank_badge = "🥉 AI RECOMMENDED — RANK #3"
            why = (
                f"<br><br><b>💡 Why Rank #3:</b><br>"
                f"Score {t['_score']}/30 — {top_score - t['_score']} pt(s) behind #1. "
                f"Best for a niche angle."
            )
        else:
            rank_badge = f"📌 Option #{rank}"
            why = ""
        
        score_comment = (
            f"<h3>{rank_badge}</h3>"
            f"<br><b>📊 Trend Score:</b> {t.get('trend_score', '?')}/10"
            f"<br><b>🛡️ Credibility Score:</b> {t.get('credibility_score', '?')}/10"
            f"<br><b>🚀 Virality Score:</b> {t.get('virality_score', '?')}/10"
            f"<br><b>📈 Total Score:</b> {t.get('_score', 0)}/30"
            f"<br><br><b>Content Angle:</b> {t.get('content_angle', 'N/A')}"
            f"<br><b>Trend Topic:</b> {t.get('trend_topic', 'N/A')}"
            f"<br><b>Sub-Pillar:</b> {t.get('sub_pillar', 'N/A')}"
            f"{why}"
            f"<br><br><i>To select: change Status → 'Topic Selected'</i>"
        )
        monday.post_update(str(sub_id), score_comment)
    
    print(f"✅ Created {len(topics)} sub-items (ranked by score, details in comments)!")
    monday.update_status(request_id, "status", "Topics Generated")

def run_finalization_stage(selected_id):
    print("=== PHASE 3: Content Finalization ===")
    monday = MondayAPI(MONDAY_API_KEY)
    groups = monday.get_board_groups(MASTER_BOARD_ID)
    cg = next((g for g in groups if "Ready" in g["title"] or "Content" in g["title"]), groups[2] if len(groups)>2 else groups[0])
    
    # Fetch subitem + parent with exact column IDs
    q = """
    query ($item_id: ID!) {
        items (ids: [$item_id]) {
            name
            board { id }
            column_values { id text value }
            parent_item {
                id
                name
                column_values { id text value }
            }
        }
    }
    """
    try:
        res = monday.query(q, {"item_id": selected_id})
        si = res["data"]["items"][0]
        pi = si.get("parent_item")
        sub_board_id = si.get("board", {}).get("id")
        
        print(f"   Subitem board: {sub_board_id} | Parent: {pi.get('name') if pi else 'None'}")
        
        # Build lookup dict for subitem columns: {column_id: text}
        sub_cols = {c["id"]: (c["text"] or "") for c in si["column_values"]}
        # Build lookup dict for parent columns
        par_cols = {c["id"]: (c["text"] or "") for c in pi["column_values"]} if pi else {}
        
        print(f"   Subitem columns: {sub_cols}")
        print(f"   Parent columns: {par_cols}")
        
        # Extract using EXACT column IDs — subitem board IDs
        topic = {
            "title":         si["name"],
            "description":   sub_cols.get("long_text_mm1wg3xz", ""),
            "platform":      sub_cols.get("dropdown_mm1wepd4", ""),
            "format":        sub_cols.get("dropdown_mm1wppt3", ""),
            "sub_pillar":    sub_cols.get("text_mm1wxd4b", ""),
            "content_angle": sub_cols.get("text_mm1wv8e3", ""),
            "trend_topic":   sub_cols.get("text_mm1wesed", ""),
            "pillar":        "",   # comes from parent
        }
        
        # Fill missing fields from parent (main board column IDs)
        if not topic["platform"]:     topic["platform"]  = par_cols.get("dropdown_mm1w7sd9", "")
        if not topic["format"]:       topic["format"]    = par_cols.get("dropdown_mm1w72b4", "")
        topic["pillar"] = par_cols.get("text_mm1w3t2c", "")
        if not topic["description"]:  topic["description"] = par_cols.get("long_text_mm1wzgth", "")
        
        print(f"   Topic resolved: {topic}")
        
        payload = generate_full_content(topic)
        if not payload:
            print("❌ generate_full_content returned None — aborting finalization")
            return
        
        print(f"   ✅ Content generated. Payload keys: {list(payload.keys())}")
        
        # Create final item in Ready Content with ALL columns filled
        col_values = {"status": {"label": "Ready to Publish"}}
        if topic.get("platform"):    col_values["dropdown_mm1w7sd9"]  = {"labels": [topic["platform"]]}
        if topic.get("format"):      col_values["dropdown_mm1w72b4"]  = {"labels": [topic["format"]]}
        if topic.get("pillar"):      col_values["text_mm1w3t2c"]      = topic["pillar"]
        if topic.get("trend_topic"): col_values["text_mm1wj52x"]      = topic["trend_topic"]
        if topic.get("description"): col_values["long_text_mm1wzgth"] = {"text": topic["description"]}
        
        final_id = monday.create_item(MASTER_BOARD_ID, cg["id"], topic["title"], column_values=json.dumps(col_values))
        print(f"   ✅ Created final item ID: {final_id}")
        
        # Post full generated content as update/comment — use dedicated method
        content_body = (
            f"<h2>📝 FINAL GENERATED CONTENT</h2>"
            f"<br><b>Platform:</b> {topic.get('platform', 'N/A')} | <b>Format:</b> {topic.get('format', 'N/A')}"
            f"<br><b>Pillar:</b> {topic.get('pillar', 'N/A')} | <b>Sub-Pillar:</b> {topic.get('sub_pillar', 'N/A')}"
            f"<br><b>Trend:</b> {topic.get('trend_topic', 'N/A')}"
            f"<br><b>Content Angle:</b> {topic.get('content_angle', 'N/A')}"
            f"<br><br><h3>📄 Post Content</h3><br>{payload.get('content', '')}"
            f"<br><br><h3>🎣 Alternative Hooks</h3><br>{payload.get('hooks', '')}"
            f"<br><br><h3>🔑 Keywords</h3><br>{payload.get('keywords', '')}"
            f"<br><br><h3>⚔️ Competitor Insights</h3><br>{payload.get('competitor_insights', '')}"
            f"<br><br><b>🎯 Engagement Score:</b> {payload.get('engagement_score', '?')}/10"
        )
        print(f"   📝 Posting update on final item {final_id}...")
        monday.post_update(str(final_id), content_body)
        # Lock subitem using its own board ID
        monday.update_status(selected_id, "status", "Content Generated", board_id=sub_board_id)
        # Set parent to Done
        if pi:
            monday.update_status(pi["id"], "status", "Done")
        print("✅ Content perfectly mapped to Monday!")
    except Exception as e:
        import traceback
        print(f"❌ Could not finalize content: {e}")
        traceback.print_exc()
def run_poll_stage():
    """Poll Monday.com board for status changes and react accordingly.
    
    Scans for:
    1. Items with status 'Ready to Generate' → triggers Phase 2 (topic generation)
    2. Subitems with status 'Topic Selected' → triggers Phase 3 (content finalization)
    """
    print("=== POLLING: Scanning Monday.com board for pending actions ===")
    monday = MondayAPI(MONDAY_API_KEY)
    
    # Fetch ALL items from the board with their subitems in one query
    # Include board { id } on subitems so we know which board they belong to
    q = """
    query($board_id: ID!) {
        boards(ids: [$board_id]) {
            items_page(limit: 100) {
                items {
                    id
                    name
                    column_values { id text value }
                    subitems {
                        id
                        name
                        column_values { id text value }
                        board { id }
                    }
                }
            }
        }
    }
    """
    try:
        res = monday.query(q, {"board_id": MASTER_BOARD_ID})
    except Exception as e:
        print(f"❌ Failed to query board: {e}")
        return
    
    items = res["data"]["boards"][0]["items_page"]["items"]
    print(f"📋 Found {len(items)} items on the board")
    
    actions_taken = 0
    
    for item in items:
        item_id = item["id"]
        item_name = item["name"]
        
        # Extract column values into a dict
        cols = {}
        for c in item["column_values"]:
            cols[c["id"]] = c["text"] or ""
        
        item_status = cols.get("status", "")
        
        # --- PHASE 2 TRIGGER: Item has "Ready to Generate" status ---
        if item_status == "Ready to Generate":
            print(f"\n🔥 FOUND: '{item_name}' (ID: {item_id}) → Status: Ready to Generate")
            
            # Extract platform, format, pillar from the item's columns
            platform = cols.get("dropdown_mm1w7sd9", "") or "LinkedIn"
            format_type = cols.get("dropdown_mm1w72b4", "") or "Post"
            pillar = cols.get("text_mm1w3t2c", "") or "General"
            
            print(f"   Platform: {platform} | Format: {format_type} | Pillar: {pillar}")
            
            # First set status to "Selecting Topic" to prevent re-processing on next poll
            try:
                monday.update_status(item_id, "status", "Selecting Topic")
                print(f"   ⏳ Status set to 'Selecting Topic' (lock acquired)")
            except Exception as e:
                print(f"   ⚠️ Could not lock item status: {e}")
                continue
            
            # Now generate topics
            run_generation_stage(item_id, platform, format_type, pillar)
            actions_taken += 1
        
        # --- PHASE 3 TRIGGER: Check subitems for "Topic Selected" status ---
        subitems = item.get("subitems", [])
        for sub in subitems:
            sub_cols = {}
            for c in sub["column_values"]:
                sub_cols[c["id"]] = c["text"] or ""
            
            sub_status = sub_cols.get("status", "")
            # Get the subitems board ID (different from main board!)
            sub_board_id = sub.get("board", {}).get("id")
            
            if sub_status == "Topic Selected":
                print(f"\n🎯 FOUND: Subitem '{sub['name']}' (ID: {sub['id']}, Board: {sub_board_id}) → Status: Topic Selected")
                
                # First set subitem status to prevent re-processing
                # Must use the SUBITEMS board ID, not the parent board ID!
                try:
                    monday.update_status(sub["id"], "status", "Content Generated", board_id=sub_board_id)
                    print(f"   ⏳ Subitem status set to 'Content Generated' (lock acquired)")
                except Exception as e:
                    print(f"   ⚠️ Could not lock subitem status: {e}")
                    continue
                
                run_finalization_stage(sub["id"])
                actions_taken += 1
    
    if actions_taken == 0:
        print("\n✅ No pending actions found. Board is up to date!")
    else:
        print(f"\n🚀 Completed {actions_taken} action(s) this poll cycle!")


def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python ai_engine.py [recommend|generate|finalize|poll]")
        sys.exit(1)
    st = sys.argv[1]
    if st == "recommend": run_recommendation_stage()
    elif st == "generate": run_generation_stage(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif st == "finalize": run_finalization_stage(sys.argv[2])
    elif st == "poll": run_poll_stage()
    else:
        print(f"❌ Unknown command: {st}")
        print("Available commands: recommend, generate, finalize, poll")
        sys.exit(1)

if __name__ == "__main__":
    main()
