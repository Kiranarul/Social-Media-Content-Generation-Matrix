import customtkinter as ctk
import threading
import sys
import os
import time
import json
from datetime import datetime
from dotenv import load_dotenv
from local_poller import run_engine_command

load_dotenv()

# Force UTF-8 stdout
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- CONFIGURATION ---
POLL_INTERVAL_S = 60

def parse_calendar_text(text):
    """Sends raw text to Gemini to parse into a structured JSON list of calendar posts."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise Exception("GEMINI_API_KEY is not configured in environment.")
    
    from google import genai
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
You are an expert scheduler and content parser for Infinitesol (a cybersecurity firm).
Read the following raw content calendar text:
---
{text}
---

Extract all content items to generate. For each item, extract:
1. day: The day of the week (e.g. Monday, Tuesday, etc., or Weekly, Repurpose)
2. title: The exact topic or title of the post
3. platform: The social media platform. Must match one of: LinkedIn, Instagram, Twitter, Facebook, Website, Email (if not clear, default to LinkedIn)
4. format: The content format. Must match one of: Post, Carousel, Reel, Video, Poll, Story, Article, Newsletter (if not clear, default to Post)
5. description: Brief context/description or instructions (like options for polls, target audience, repurpose notes, etc.)
6. prompt_guideline: A specific generation instruction based on the format:
   - For Reels/Video: "Generate a highly dynamic short-form video script including visual scene directions, on-screen text overlays, and an engaging spoken voiceover."
   - For Carousels: "Generate a slide-by-slide outline (Slide 1 to 7) detailing slide title, visual concept, and slide text."
   - For Polls: "Generate a caption introducing the poll, list the options, and ask users to comment."
   - For Articles/Newsletters: "Write a structured long-form article using markdown headings and bullet points."
   - For Posts: "Write a punchy social media post with a clear hook, brief body paragraphs, and a call-to-action."

Output a STRICT JSON array:
[
  {{
    "day": "string",
    "title": "string",
    "platform": "string",
    "format": "string",
    "description": "string",
    "prompt_guideline": "string"
  }}
]
RAW JSON ONLY. No markdown wrappers. Ensure no unescaped control characters or unescaped quotes in the content JSON values.
"""
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text.strip()
    if response.startswith("```json"): response = response[7:-3].strip()
    elif response.startswith("```"): response = response[3:-3].strip()
    return json.loads(response)

class AutomationManager:
    """Manages the lifecycle of background polling tasks."""
    def __init__(self, log_callback):
        self.is_polling = False
        self.log_callback = log_callback
        self.thread = None

    def start_polling(self):
        if not self.is_polling:
            self.is_polling = True
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
            return True
        return False

    def stop_polling(self):
        self.is_polling = False

    def _run_loop(self):
        self.log_callback(">>> Local Poller Engine: ACTIVATED <<<\nMonitoring board for status changes...", "info")
        while self.is_polling:
            output = run_engine_command(["poll"])
            self.log_callback(output, "poll_result")
            
            for _ in range(POLL_INTERVAL_S):
                if not self.is_polling:
                    break
                time.sleep(1)
        
        self.log_callback(">>> Local Poller Engine: DEACTIVATED <<<", "warning")

    def manual_recommend(self):
        """Immediately triggers the AI recommendation engine."""
        self.log_callback(">>> Triggering immediate AI Strategy Recommendation...", "action")
        output = run_engine_command(["recommend"])
        self.log_callback(output, "rec_result")

class DashboardGUI(ctk.CTk):
    """Modern UI for the AI Content Factory Management with Bulk Generator Support."""
    def __init__(self):
        super().__init__()

        # --- Window Setup ---
        self.title("Infinitesol AI Content Matrix | Control Center")
        self.geometry("1020x720")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.manager = AutomationManager(self.update_log)
        self.parsed_items = []

        # --- Sidebar (Navigation & Controls) ---
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        self.brand_label = ctk.CTkLabel(self.sidebar, text="%s" % "INFINITESOL", 
                                        font=ctk.CTkFont(size=22, weight="bold"))
        self.brand_label.pack(pady=(30, 5))
        self.sub_brand = ctk.CTkLabel(self.sidebar, text="AI CONTENT FACTORY", 
                                      font=ctk.CTkFont(size=10, weight="normal"))
        self.sub_brand.pack(pady=(0, 40))

        # Status Badge
        self.status_box = ctk.CTkFrame(self.sidebar, fg_color="#1a1a1a", height=60)
        self.status_box.pack(pady=10, padx=20, fill="x")
        self.status_label = ctk.CTkLabel(self.status_box, text="● SYSTEM IDLE", 
                                          text_color="#888", font=ctk.CTkFont(weight="bold"))
        self.status_label.pack(expand=True)

        # Action Buttons
        self.btn_start = ctk.CTkButton(self.sidebar, text="START AUTOMATION", command=self.start_automation,
                                         fg_color="#2e7d32", hover_color="#1b5e20", height=45)
        self.btn_start.pack(pady=15, padx=20, fill="x")

        self.btn_stop = ctk.CTkButton(self.sidebar, text="STOP POLLING", command=self.stop_automation,
                                        fg_color="#c62828", hover_color="#b71c1c", height=45, state="disabled")
        self.btn_stop.pack(pady=15, padx=20, fill="x")

        self.btn_recommend = ctk.CTkButton(self.sidebar, text="RECOMMEND NOW", command=self.trigger_recommend,
                                             fg_color="#1565c0", hover_color="#0d47a1", height=45)
        self.btn_recommend.pack(pady=15, padx=20, fill="x")

        self.exit_btn = ctk.CTkButton(self.sidebar, text="CLOSE WINDOW", command=self.shutdown,
                                      fg_color="transparent", border_width=1)
        self.exit_btn.pack(side="bottom", pady=30, padx=20, fill="x")

        # --- Main Workspace Tabview ---
        self.tabview = ctk.CTkTabview(self, corner_radius=10)
        self.tabview.pack(side="right", fill="both", expand=True, padx=20, pady=20)
        
        self.tab_live = self.tabview.add("Live Feed & Controls")
        self.tab_bulk = self.tabview.add("Bulk Creator")

        # --- Live Feed Tab ---
        self.container = ctk.CTkFrame(self.tab_live, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=10, pady=10)

        self.header = ctk.CTkLabel(self.container, text="AUTOMATION ENGINE LIVE FEED", 
                                   font=ctk.CTkFont(size=14, weight="bold"))
        self.header.pack(anchor="w", pady=(0, 10))

        self.log_view = ctk.CTkTextbox(self.container, font=("Consolas", 12), border_width=0, corner_radius=10)
        self.log_view.pack(fill="both", expand=True)
        self.log_view.configure(state="normal")
        self.log_view.insert("0.0", f"[{datetime.now().strftime('%H:%M:%S')}] Application Initialization Complete.\nWaiting for user interaction...\n" + "—"*60 + "\n\n")
        self.log_view.configure(state="disabled")

        # --- Bulk Creator Tab ---
        self.bulk_container = ctk.CTkFrame(self.tab_bulk, fg_color="transparent")
        self.bulk_container.pack(fill="both", expand=True, padx=10, pady=10)

        self.bulk_header = ctk.CTkLabel(self.bulk_container, text="BULK CONTENT GENERATOR (PASTE WEEKLY PLAN)", 
                                        font=ctk.CTkFont(size=14, weight="bold"))
        self.bulk_header.pack(anchor="w", pady=(0, 10))

        # Split frame
        self.split_frame = ctk.CTkFrame(self.bulk_container, fg_color="transparent")
        self.split_frame.pack(fill="both", expand=True)

        # Left panel: Input text box
        self.left_panel = ctk.CTkFrame(self.split_frame, fg_color="transparent")
        self.left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.input_label = ctk.CTkLabel(self.left_panel, text="1. Paste Raw Text Plan Here:")
        self.input_label.pack(anchor="w", pady=(0, 5))

        self.calendar_input = ctk.CTkTextbox(self.left_panel, font=("Consolas", 11), border_width=1, corner_radius=8)
        self.calendar_input.pack(fill="both", expand=True, pady=(0, 10))
        self.calendar_input.insert("1.0", "Paste your text calendar here...")

        self.btn_parse = ctk.CTkButton(self.left_panel, text="PARSE & PREVIEW", command=self.parse_calendar,
                                       fg_color="#1565c0", hover_color="#0d47a1", height=40)
        self.btn_parse.pack(fill="x")

        # Right panel: Preview text box
        self.right_panel = ctk.CTkFrame(self.split_frame, fg_color="transparent")
        self.right_panel.pack(side="right", fill="both", expand=True, padx=(10, 0))

        self.preview_label = ctk.CTkLabel(self.right_panel, text="2. Parsed Structure Preview:")
        self.preview_label.pack(anchor="w", pady=(0, 5))

        self.preview_box = ctk.CTkTextbox(self.right_panel, font=("Consolas", 11), border_width=1, corner_radius=8)
        self.preview_box.pack(fill="both", expand=True, pady=(0, 10))
        self.preview_box.configure(state="normal")
        self.preview_box.insert("1.0", "Parsed items will preview here...")
        self.preview_box.configure(state="disabled")

        self.btn_run_bulk = ctk.CTkButton(self.right_panel, text="RUN BULK GENERATION", command=self.run_bulk_generation,
                                          fg_color="#2e7d32", hover_color="#1b5e20", height=40, state="disabled")
        self.btn_run_bulk.pack(fill="x")

        # Status text below panels
        self.bulk_status = ctk.CTkLabel(self.bulk_container, text="Status: Ready", font=ctk.CTkFont(weight="bold"))
        self.bulk_status.pack(anchor="w", pady=(10, 0))

    # --- ACTIONS ---
    def update_log(self, text, event_type="info"):
        """Thread-safe update of the log window."""
        def append():
            self.log_view.configure(state="normal")
            self.log_view.insert("end", text + "\n\n")
            self.log_view.see("end")
            self.log_view.configure(state="disabled")
        
        self.after(0, append)

    def update_bulk_status(self, message, color="white"):
        """Updates the status label at the bottom of the Bulk Creator tab."""
        def update():
            color_map = {
                "white": "#ffffff",
                "red": "#f44336",
                "green": "#4caf50",
                "orange": "#ff9800"
            }
            self.bulk_status.configure(text=f"Status: {message}", text_color=color_map.get(color, color))
        self.after(0, update)

    def set_preview_content(self, text):
        """Helper to write preview content cleanly."""
        def update():
            self.preview_box.configure(state="normal")
            self.preview_box.delete("1.0", "end")
            self.preview_box.insert("1.0", text)
            self.preview_box.configure(state="disabled")
        self.after(0, update)

    def start_automation(self):
        if self.manager.start_polling():
            self.btn_start.configure(state="disabled")
            self.btn_stop.configure(state="normal")
            self.status_label.configure(text="● AUTO-POLLING LIVE", text_color="#2e7d32")

    def stop_automation(self):
        self.manager.stop_polling()
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.status_label.configure(text="● SYSTEM IDLE", text_color="#888")

    def trigger_recommend(self):
        threading.Thread(target=self.manager.manual_recommend, daemon=True).start()

    def parse_calendar(self):
        """Runs the Gemini calendar parser in a background thread."""
        text = self.calendar_input.get("1.0", "end").strip()
        if not text or text == "Paste your text calendar here...":
            self.update_bulk_status("❌ Please paste some calendar text first.", "red")
            return
        
        self.btn_parse.configure(state="disabled", text="PARSING...")
        self.btn_run_bulk.configure(state="disabled")
        self.update_bulk_status("⏳ Parsing calendar text with Gemini AI...", "orange")
        
        def run():
            try:
                parsed = parse_calendar_text(text)
                self.parsed_items = parsed
                
                # Create a readable preview
                preview_text = ""
                for idx, item in enumerate(parsed):
                    preview_text += f"[{idx+1}] Day: {item.get('day', 'N/A')}\n"
                    preview_text += f"    Platform: {item.get('platform', 'N/A')} | Format: {item.get('format', 'N/A')}\n"
                    preview_text += f"    Topic: {item.get('title', 'N/A')}\n"
                    preview_text += f"    Desc: {item.get('description', 'N/A')}\n\n"
                
                self.set_preview_content(preview_text)
                self.update_bulk_status(f"✅ Successfully parsed {len(parsed)} items! Ready to generate.", "green")
                self.after(0, lambda: self.btn_run_bulk.configure(state="normal"))
            except Exception as e:
                self.set_preview_content(f"Error parsing text:\n{str(e)}")
                self.update_bulk_status("❌ Parsing failed. Check API key or connection.", "red")
            finally:
                self.after(0, lambda: self.btn_parse.configure(state="normal", text="PARSE & PREVIEW"))
        
        threading.Thread(target=run, daemon=True).start()

    def run_bulk_generation(self):
        """Runs the bulk content generation loop in a background thread."""
        if not self.parsed_items:
            self.update_bulk_status("❌ No parsed items to generate.", "red")
            return
        
        self.btn_run_bulk.configure(state="disabled")
        self.btn_parse.configure(state="disabled")
        self.tabview.set("Live Feed & Controls")
        
        def run():
            # Local imports to avoid start-up overhead
            from google import genai
            from ai_engine import MondayAPI, MASTER_BOARD_ID, MONDAY_API_KEY
            
            api_key = os.getenv("GEMINI_API_KEY")
            client = genai.Client(api_key=api_key)
            monday_api = MondayAPI(MONDAY_API_KEY)
            
            # Board Config
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
            
            total = len(self.parsed_items)
            self.update_log(f">>> Starting Bulk Content Generation for {total} items... <<<", "action")
            
            for idx, item in enumerate(self.parsed_items):
                progress_msg = f"⏳ [{idx+1}/{total}] Processing: {item['title']} ({item['platform']} {item['format']})"
                self.update_log(progress_msg, "info")
                self.update_bulk_status(progress_msg, "orange")
                
                # Format-specific guidelines mapping if missing
                guideline = item.get("prompt_guideline", "")
                if not guideline:
                    fmt = item.get("format", "").lower()
                    if fmt in ["reel", "video"]:
                        guideline = "Generate a highly dynamic short-form video script including visual scene directions, on-screen text overlays, and an engaging spoken voiceover."
                    elif fmt == "carousel":
                        guideline = "Generate a slide-by-slide outline (Slide 1 to 7) detailing slide title, visual concept, and slide text."
                    elif fmt == "poll":
                        guideline = "Generate a caption introducing the poll, list the options, and ask users to comment."
                    elif fmt in ["article", "newsletter"]:
                        guideline = "Write a structured long-form article using markdown headings and bullet points."
                    else:
                        guideline = "Write a punchy social media post with a clear hook, brief body paragraphs, and a call-to-action."

                # 1. Gemini Content Generation
                payload = None
                backoff = 2
                for attempt in range(1, 4):
                    try:
                        prompt = f"""
You are an elite content strategist for Infinitesol (a modern cybersecurity firm).
Determine a fitting Content Pillar, Sub-pillar, Content Angle, and Trend Topic for the following post topic:
Topic: "{item['title']}"
Platform: {item['platform']}
Format: {item['format']}
Description/Context: {item['description']}

Format-Specific Instruction: {guideline}

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
                        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text.strip()
                        if response.startswith("```json"): response = response[7:-3].strip()
                        elif response.startswith("```"): response = response[3:-3].strip()
                        payload = json.loads(response)
                        break
                    except Exception as e:
                        self.update_log(f"   ⚠️ Attempt {attempt} failed: {e}", "warning")
                        if attempt == 3:
                            break
                        time.sleep(backoff)
                        backoff *= 2
                
                if not payload:
                    self.update_log(f"❌ Failed to generate: {item['title']}", "error")
                    continue
                
                # 2. Upload to Monday.com
                try:
                    parent_name = f"📅 {item['day']} - {item['title']}"
                    parent_col_values = {
                        STATUS_COL: {"label": "Done"},
                        PLATFORM_COL: {"labels": [item["platform"]]},
                        FORMAT_COL: {"labels": [item["format"]]},
                        PILLAR_COL: payload.get("pillar", "General"),
                        DESC_COL: {"text": item["description"]},
                        TREND_COL: payload.get("trend_topic", "")
                    }
                    parent_id = monday_api.create_item(MASTER_BOARD_ID, HISTORY_GROUP, parent_name, column_values=json.dumps(parent_col_values))
                    
                    sub_col_values = {
                        SUB_STATUS_COL: {"label": "Content Generated"},
                        SUB_PLATFORM_COL: {"labels": [item["platform"]]},
                        SUB_FORMAT_COL: {"labels": [item["format"]]},
                        SUB_PILLAR_COL: payload.get("sub_pillar", ""),
                        SUB_ANGLE_COL: payload.get("content_angle", ""),
                        SUB_TREND_COL: payload.get("trend_topic", ""),
                        SUB_DESC_COL: {"text": item["description"]}
                    }
                    monday_api.create_item(MASTER_BOARD_ID, "", item["title"], parent_id=parent_id, column_values=json.dumps(sub_col_values))
                    
                    final_col_values = {
                        STATUS_COL: {"label": "Ready to Publish"},
                        PLATFORM_COL: {"labels": [item["platform"]]},
                        FORMAT_COL: {"labels": [item["format"]]},
                        PILLAR_COL: payload.get("pillar", "General"),
                        DESC_COL: {"text": item["description"]},
                        TREND_COL: payload.get("trend_topic", "")
                    }
                    final_id = monday_api.create_item(MASTER_BOARD_ID, READY_CONTENT_GROUP, item["title"], column_values=json.dumps(final_col_values))
                    
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
                    monday_api.post_update(final_id, content_body)
                    self.update_log(f"   ✅ Successfully posted: '{item['title']}' (ID: {final_id})", "info")
                except Exception as ex:
                    self.update_log(f"❌ Monday.com API error for '{item['title']}': {ex}", "error")
                
                time.sleep(1)
            
            self.update_log("🎉 Bulk Generation Completed Successfully!", "info")
            self.update_bulk_status("🎉 Completed all bulk generation successfully!", "green")
            self.after(0, lambda: self.btn_parse.configure(state="normal"))
            self.after(0, lambda: self.btn_run_bulk.configure(state="disabled"))
            self.parsed_items = []
            
        threading.Thread(target=run, daemon=True).start()

    def shutdown(self):
        self.manager.stop_polling()
        self.destroy()
        sys.exit(0)

if __name__ == "__main__":
    app = DashboardGUI()
    app.protocol("WM_DELETE_WINDOW", app.shutdown)
    app.mainloop()
