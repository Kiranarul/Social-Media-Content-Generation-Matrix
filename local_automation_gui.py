import customtkinter as ctk
import threading
import sys
import os
import time
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from tkcalendar import DateEntry
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
SCHEDULE_FILE = "schedule_config.json"
APPROVED_TOPICS_FILE = "approved_topics_memory.json"
MODEL_ID = "gemma-4-31b-it"

PLATFORMS = ["LinkedIn", "Instagram", "Twitter", "Facebook", "Website", "Email"]
FORMATS = ["Post", "Carousel", "Reel", "Video", "Poll", "Story", "Article", "Newsletter"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise Exception("GEMINI_API_KEY is not configured in environment.")
    from google import genai
    return genai.Client(api_key=api_key)

def parse_calendar_text(text):
    """Sends raw text to Gemini to parse into a structured JSON list of calendar posts."""
    client = get_gemini_client()
    prompt = f"""
You are an expert scheduler and content parser for Infinitesol (a cybersecurity firm).
Read the following raw content calendar text:
---
{text}
---

Extract all content items to generate. Output a STRICT JSON array:
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
RAW JSON ONLY. No markdown wrappers. Ensure no unescaped control characters or unescaped quotes.
"""
    response = client.models.generate_content(model=MODEL_ID, contents=prompt).text.strip()
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
        self.log_callback(">>> Triggering immediate AI Strategy Recommendation...", "action")
        output = run_engine_command(["recommend"])
        self.log_callback(output, "rec_result")

class DashboardGUI(ctk.CTk):
    """Modern UI for the AI Content Factory Management with Bulk Generator Support."""
    def __init__(self):
        super().__init__()

        # --- Window Setup ---
        self.title("Infinitesol AI Content Matrix | Control Center")
        self.geometry("1200x800")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.manager = AutomationManager(self.update_log)
        self.parsed_items = []
        self.schedule_config = self.load_schedule()
        self.generated_topics = []
        self.approved_topics = self.load_approved_topics()

        # --- Sidebar ---
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        self.brand_label = ctk.CTkLabel(self.sidebar, text="INFINITESOL", font=ctk.CTkFont(size=22, weight="bold"))
        self.brand_label.pack(pady=(30, 5))
        self.sub_brand = ctk.CTkLabel(self.sidebar, text="AI CONTENT FACTORY", font=ctk.CTkFont(size=10, weight="normal"))
        self.sub_brand.pack(pady=(0, 40))

        # Status Badge
        self.status_box = ctk.CTkFrame(self.sidebar, fg_color="#1a1a1a", height=60)
        self.status_box.pack(pady=10, padx=20, fill="x")
        self.status_label = ctk.CTkLabel(self.status_box, text="● SYSTEM IDLE", text_color="#888", font=ctk.CTkFont(weight="bold"))
        self.status_label.pack(expand=True)

        self.btn_start = ctk.CTkButton(self.sidebar, text="START AUTOMATION", command=self.start_automation, fg_color="#2e7d32", hover_color="#1b5e20", height=45)
        self.btn_start.pack(pady=15, padx=20, fill="x")

        self.btn_stop = ctk.CTkButton(self.sidebar, text="STOP POLLING", command=self.stop_automation, fg_color="#c62828", hover_color="#b71c1c", height=45, state="disabled")
        self.btn_stop.pack(pady=15, padx=20, fill="x")

        self.btn_recommend = ctk.CTkButton(self.sidebar, text="RECOMMEND NOW", command=self.trigger_recommend, fg_color="#1565c0", hover_color="#0d47a1", height=45)
        self.btn_recommend.pack(pady=15, padx=20, fill="x")

        self.exit_btn = ctk.CTkButton(self.sidebar, text="CLOSE WINDOW", command=self.shutdown, fg_color="transparent", border_width=1)
        self.exit_btn.pack(side="bottom", pady=30, padx=20, fill="x")

        # --- Main Workspace Tabview ---
        self.tabview = ctk.CTkTabview(self, corner_radius=10)
        self.tabview.pack(side="right", fill="both", expand=True, padx=20, pady=20)
        
        self.tab_live = self.tabview.add("Live Feed & Controls")
        self.tab_schedule = self.tabview.add("Schedule Configurator")
        self.tab_topic = self.tabview.add("Topic Generator")
        self.tab_editor = self.tabview.add("Content Editor")
        self.tab_bulk = self.tabview.add("Bulk Creator")

        self.setup_live_tab()
        self.setup_schedule_tab()
        self.setup_topic_tab()
        self.setup_editor_tab()
        self.setup_bulk_tab()

    def load_schedule(self):
        if os.path.exists(SCHEDULE_FILE):
            try:
                with open(SCHEDULE_FILE, "r") as f:
                    return json.load(f)
            except:
                pass
        return {day: [] for day in DAYS}

    def save_schedule(self):
        with open(SCHEDULE_FILE, "w") as f:
            json.dump(self.schedule_config, f, indent=4)

    def load_approved_topics(self):
        if os.path.exists(APPROVED_TOPICS_FILE):
            try:
                with open(APPROVED_TOPICS_FILE, "r") as f:
                    return json.load(f)
            except:
                pass
        return []

    def save_approved_topics(self):
        with open(APPROVED_TOPICS_FILE, "w") as f:
            json.dump(self.approved_topics, f, indent=4)

    # --- SETUP TABS ---
    def setup_live_tab(self):
        container = ctk.CTkFrame(self.tab_live, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=10)
        header = ctk.CTkLabel(container, text="AUTOMATION ENGINE LIVE FEED", font=ctk.CTkFont(size=14, weight="bold"))
        header.pack(anchor="w", pady=(0, 10))
        self.log_view = ctk.CTkTextbox(container, font=("Consolas", 12), border_width=0, corner_radius=10)
        self.log_view.pack(fill="both", expand=True)
        self.log_view.configure(state="normal")
        self.log_view.insert("0.0", f"[{datetime.now().strftime('%H:%M:%S')}] Application Initialization Complete.\nWaiting for user interaction...\n" + "—"*60 + "\n\n")
        self.log_view.configure(state="disabled")

    def setup_schedule_tab(self):
        container = ctk.CTkFrame(self.tab_schedule, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=10)
        
        header = ctk.CTkLabel(container, text="WEEKLY SCHEDULE CONFIGURATOR", font=ctk.CTkFont(size=14, weight="bold"))
        header.pack(anchor="w", pady=(0, 10))

        top_frame = ctk.CTkFrame(container, fg_color="transparent")
        top_frame.pack(fill="x", pady=5)

        self.sched_day_var = ctk.StringVar(value="Monday")
        ctk.CTkLabel(top_frame, text="Day:").pack(side="left", padx=5)
        ctk.CTkOptionMenu(top_frame, variable=self.sched_day_var, values=DAYS, command=self.refresh_schedule_list).pack(side="left", padx=5)

        self.sched_plat_var = ctk.StringVar(value="LinkedIn")
        ctk.CTkLabel(top_frame, text="Platform:").pack(side="left", padx=5)
        ctk.CTkOptionMenu(top_frame, variable=self.sched_plat_var, values=PLATFORMS).pack(side="left", padx=5)

        self.sched_form_var = ctk.StringVar(value="Post")
        ctk.CTkLabel(top_frame, text="Format:").pack(side="left", padx=5)
        ctk.CTkOptionMenu(top_frame, variable=self.sched_form_var, values=FORMATS).pack(side="left", padx=5)

        ctk.CTkButton(top_frame, text="Add Rule", command=self.add_schedule_rule, fg_color="#1565c0").pack(side="left", padx=20)

        self.sched_list_frame = ctk.CTkScrollableFrame(container)
        self.sched_list_frame.pack(fill="both", expand=True, pady=10)

        self.refresh_schedule_list(self.sched_day_var.get())

    def add_schedule_rule(self):
        day = self.sched_day_var.get()
        plat = self.sched_plat_var.get()
        form = self.sched_form_var.get()
        self.schedule_config[day].append({"platform": plat, "format": form})
        self.save_schedule()
        self.refresh_schedule_list(day)

    def remove_schedule_rule(self, day, idx):
        if 0 <= idx < len(self.schedule_config[day]):
            self.schedule_config[day].pop(idx)
            self.save_schedule()
            self.refresh_schedule_list(day)

    def refresh_schedule_list(self, day):
        for widget in self.sched_list_frame.winfo_children():
            widget.destroy()
        
        rules = self.schedule_config.get(day, [])
        if not rules:
            ctk.CTkLabel(self.sched_list_frame, text=f"No rules for {day}.").pack(pady=10)
        else:
            for i, rule in enumerate(rules):
                row = ctk.CTkFrame(self.sched_list_frame)
                row.pack(fill="x", pady=2, padx=5)
                lbl = ctk.CTkLabel(row, text=f"{rule['platform']} - {rule['format']}")
                lbl.pack(side="left", padx=10, pady=5)
                btn = ctk.CTkButton(row, text="Remove", width=60, fg_color="#c62828", hover_color="#b71c1c", command=lambda d=day, idx=i: self.remove_schedule_rule(d, idx))
                btn.pack(side="right", padx=10, pady=5)

    def setup_topic_tab(self):
        container = ctk.CTkFrame(self.tab_topic, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=10)

        header = ctk.CTkLabel(container, text="TOPIC GENERATOR (Based on Schedule)", font=ctk.CTkFont(size=14, weight="bold"))
        header.pack(anchor="w", pady=(0, 10))

        top_frame = ctk.CTkFrame(container, fg_color="transparent")
        top_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(top_frame, text="From Date:").pack(side="left", padx=5)
        self.topic_date_from = DateEntry(top_frame, width=12, background='darkblue', foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        self.topic_date_from.pack(side="left", padx=5)
        self.topic_date_from.set_date(datetime.now().date())

        ctk.CTkLabel(top_frame, text="To Date:").pack(side="left", padx=5)
        self.topic_date_to = DateEntry(top_frame, width=12, background='darkblue', foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        self.topic_date_to.pack(side="left", padx=5)
        self.topic_date_to.set_date((datetime.now() + timedelta(days=6)).date())

        context_frame = ctk.CTkFrame(container, fg_color="transparent")
        context_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(context_frame, text="Special Events / Context (Optional):").pack(side="left", padx=5)
        self.topic_context_entry = ctk.CTkEntry(context_frame, placeholder_text="e.g., Company Anniversary on Friday...", width=400)
        self.topic_context_entry.pack(side="left", padx=5, fill="x", expand=True)

        promo_frame = ctk.CTkFrame(container, fg_color="transparent")
        promo_frame.pack(fill="x", pady=5)
        self.cross_promo_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(promo_frame, text="Enable Cross-Promotion", variable=self.cross_promo_var).pack(side="left", padx=5)
        self.topic_promo_entry = ctk.CTkEntry(promo_frame, placeholder_text="e.g. Link Website to LinkedIn, Twitter...", width=400)
        self.topic_promo_entry.pack(side="left", padx=5, fill="x", expand=True)
        
        # Load memory for cross promotion
        saved_promo = self.schedule_config.get("cross_promo_memory", "")
        if saved_promo:
            self.topic_promo_entry.insert(0, saved_promo)

        self.btn_gen_topics = ctk.CTkButton(top_frame, text="Generate Topics for Date", command=self.generate_topics, fg_color="#1565c0")
        self.btn_gen_topics.pack(side="left", padx=20)

        self.topic_status = ctk.CTkLabel(top_frame, text="", text_color="#ff9800")
        self.topic_status.pack(side="left", padx=10)

        self.topics_frame = ctk.CTkScrollableFrame(container)
        self.topics_frame.pack(fill="both", expand=True, pady=10)

    def generate_topics(self):
        # Save cross promotion memory
        self.schedule_config["cross_promo_memory"] = self.topic_promo_entry.get().strip()
        self.save_schedule()

        from_dt = datetime.combine(self.topic_date_from.get_date(), datetime.min.time())
        to_dt = datetime.combine(self.topic_date_to.get_date(), datetime.min.time())
        
        from_str = from_dt.strftime("%Y-%m-%d")
        to_str = to_dt.strftime("%Y-%m-%d")
        
        if to_dt < from_dt:
            self.topic_status.configure(text="❌ 'To' date must be after 'From' date.")
            return

        all_rules = []
        current_dt = from_dt
        while current_dt <= to_dt:
            day_name = current_dt.strftime("%A")
            rules = self.schedule_config.get(day_name, [])
            for r in rules:
                all_rules.append({
                    "date": current_dt.strftime("%Y-%m-%d (%A)"),
                    "platform": r["platform"],
                    "format": r["format"]
                })
            current_dt += timedelta(days=1)
            
        if not all_rules:
            self.topic_status.configure(text="No schedule rules found in that date range.")
            return
            
        context_text = self.topic_context_entry.get().strip()
        
        enable_promo = self.cross_promo_var.get()
        promo_text = self.topic_promo_entry.get().strip()
        
        if enable_promo:
            if promo_text:
                cross_promo_instruction = f"2. Cross-Promote: {promo_text}"
            else:
                cross_promo_instruction = "2. Cross-Promote: If there is an Article/Newsletter/Blog on one day, other posts on adjacent days should act as teasers or follow-ups driving traffic to it."
        else:
            cross_promo_instruction = "2. Do NOT cross-promote. Treat each post independently."
            
        self.btn_gen_topics.configure(state="disabled")
        self.topic_status.configure(text="Generating topics with Gemini...")

        def run():
            try:
                client = get_gemini_client()
                prompt = f"""
You are an expert cybersecurity content strategist for Infinitesol.
I need a cohesive content plan spanning from {from_str} to {to_str}.

Required Schedule Items:
{json.dumps(all_rules, indent=2)}

Additional Context/Events to incorporate:
{context_text if context_text else "None"}

Guidelines:
1. Ensure the week flows logically.
{cross_promo_instruction}
3. Thematic Consistency: Build upon events, align with themes (e.g. Service Promotion Tuesday), and make general reach content engaging.
4. Output a JSON array of objects. Each object MUST include 'date', 'platform', 'format', 'title', and 'description' (a 2-sentence summary). The array must match the exact number and order of items in the Required Schedule.

RAW JSON ARRAY ONLY. NO MARKDOWN. Ensure no unescaped control characters.
"""
                resp = client.models.generate_content(model=MODEL_ID, contents=prompt).text.strip()
                if resp.startswith("```json"): resp = resp[7:-3].strip()
                elif resp.startswith("```"): resp = resp[3:-3].strip()
                
                new_topics = json.loads(resp)
                self.generated_topics = new_topics
                self.after(0, self.render_generated_topics)
                self.after(0, lambda: self.topic_status.configure(text="✅ Topics generated!"))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda msg=err_msg: self.topic_status.configure(text=f"❌ Error: {msg}"))
            finally:
                self.after(0, lambda: self.btn_gen_topics.configure(state="normal"))
                
        threading.Thread(target=run, daemon=True).start()

    def render_generated_topics(self):
        for widget in self.topics_frame.winfo_children():
            widget.destroy()

        for idx, t in enumerate(self.generated_topics):
            f = ctk.CTkFrame(self.topics_frame)
            f.pack(fill="x", pady=5, padx=5)
            
            top_row = ctk.CTkFrame(f, fg_color="transparent")
            top_row.pack(fill="x", padx=5, pady=5)
            
            ctk.CTkLabel(top_row, text=f"[{t.get('date', 'Unknown')}] {t.get('platform')} - {t.get('format')}", font=ctk.CTkFont(weight="bold")).pack(side="left")
            ctk.CTkLabel(top_row, text=f" | {t.get('title', 'No Title')}").pack(side="left", padx=10)
            
            btn = ctk.CTkButton(top_row, text="Approve & Send to Editor", fg_color="#2e7d32", 
                                command=lambda item=t: self.approve_topic(item))
            btn.pack(side="right")
            
            desc_lbl = ctk.CTkLabel(f, text=t.get('description', ''), wraplength=800, justify="left")
            desc_lbl.pack(fill="x", padx=10, pady=(0, 10))

    def approve_topic(self, item):
        # Add the target date for tracking
        item['target_date'] = item.get('date', 'Unknown')
        self.approved_topics.append(item)
        self.save_approved_topics()
        self.topic_status.configure(text=f"✅ Approved: {item.get('title')}")
        self.refresh_editor_topic_list()

    def setup_editor_tab(self):
        container = ctk.CTkFrame(self.tab_editor, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=10)
        
        header = ctk.CTkLabel(container, text="CONTENT EDITOR & PUBLISHER", font=ctk.CTkFont(size=14, weight="bold"))
        header.pack(anchor="w", pady=(0, 10))

        top_frame = ctk.CTkFrame(container, fg_color="transparent")
        top_frame.pack(fill="x", pady=5)
        
        self.editor_topic_var = ctk.StringVar(value="Select an Approved Topic...")
        self.editor_topic_menu = ctk.CTkOptionMenu(top_frame, variable=self.editor_topic_var, values=["Select an Approved Topic..."], width=400)
        self.editor_topic_menu.pack(side="left", padx=5)

        self.btn_gen_content = ctk.CTkButton(top_frame, text="Generate Content", command=self.generate_content_for_editor, fg_color="#1565c0")
        self.btn_gen_content.pack(side="left", padx=10)

        self.editor_status = ctk.CTkLabel(top_frame, text="", text_color="#ff9800")
        self.editor_status.pack(side="left", padx=10)

        # Editor Area
        self.editor_text = ctk.CTkTextbox(container, font=("Consolas", 12), border_width=1, corner_radius=5)
        self.editor_text.pack(fill="both", expand=True, pady=10)

        bot_frame = ctk.CTkFrame(container, fg_color="transparent")
        bot_frame.pack(fill="x", pady=5)

        self.btn_clear_memory = ctk.CTkButton(bot_frame, text="CLEAR TOPICS MEMORY", command=self.clear_approved_topics, fg_color="#c62828", hover_color="#b71c1c", height=40)
        self.btn_clear_memory.pack(side="left", padx=10)

        self.btn_push = ctk.CTkButton(bot_frame, text="SAVE & PUSH TO MONDAY.COM", command=self.push_to_monday, fg_color="#2e7d32", height=40)
        self.btn_push.pack(side="right", padx=10)
        
        self.current_editing_payload = None
        self.current_editing_item = None

    def clear_approved_topics(self):
        self.approved_topics = []
        self.save_approved_topics()
        self.editor_topic_var.set("Select an Approved Topic...")
        self.refresh_editor_topic_list()
        self.editor_status.configure(text="✅ Cleared approved topics memory.")

    def refresh_editor_topic_list(self):
        if not self.approved_topics:
            values = ["Select an Approved Topic..."]
        else:
            values = [f"[{i}] {t['target_date']} | {t['platform']} - {t['title'][:40]}" for i, t in enumerate(self.approved_topics)]
        
        self.editor_topic_menu.configure(values=values)
        if self.approved_topics:
            self.editor_topic_var.set(values[-1])

    def generate_content_for_editor(self):
        sel = self.editor_topic_var.get()
        if sel.startswith("Select"):
            return
        
        idx = int(sel.split("]")[0].replace("[", ""))
        item = self.approved_topics[idx]
        self.current_editing_item = item
        
        self.btn_gen_content.configure(state="disabled")
        self.editor_status.configure(text="Generating rich content...")
        
        def run():
            try:
                client = get_gemini_client()
                guideline = item.get("prompt_guideline", "")
                if not guideline:
                    fmt = item.get("format", "").lower()
                    if fmt in ["reel", "video"]: guideline = "Generate a highly dynamic short-form video script including visual scene directions, on-screen text overlays, and an engaging spoken voiceover."
                    elif fmt == "carousel": guideline = "Generate a slide-by-slide outline (Slide 1 to 7) detailing slide title, visual concept, and slide text."
                    elif fmt == "poll": guideline = "Generate a caption introducing the poll, list the options, and ask users to comment."
                    elif fmt in ["article", "newsletter"]: guideline = "Write a structured long-form article with clear spacing and bullet points (use standard dashes, no markdown asterisks)."
                    else: guideline = "Write a punchy social media post with a clear hook, brief body paragraphs, and a call-to-action."

                prompt = f"""
You are an elite content strategist for Infinitesol.
Topic: "{item.get('title')}"
Platform: {item['platform']}
Format: {item['format']}
Description/Context: {item.get('description')}

Instruction: {guideline}

CRITICAL FORMATTING RULE: Do NOT use ANY markdown formatting (no hashtags # for headers, no stars * or ** for bold/italics). Output plain text formatted with standard line breaks only.

Please generate:
1. content: The full formatted post or script.
2. hooks: 5 alternative hooks
3. keywords: SEO keywords
4. pillar: High-level content pillar (e.g. Threat Awareness)
5. sub_pillar: Specific sub-pillar
6. trend_topic: Industry trend linked to it

Output STRICT JSON:
{{
  "pillar": "string",
  "sub_pillar": "string",
  "trend_topic": "string",
  "content": "string",
  "hooks": "string",
  "keywords": "string"
}}
RAW JSON ONLY.
"""
                resp = client.models.generate_content(model=MODEL_ID, contents=prompt).text.strip()
                if resp.startswith("```json"): resp = resp[7:-3].strip()
                elif resp.startswith("```"): resp = resp[3:-3].strip()
                
                payload = json.loads(resp)
                self.current_editing_payload = payload
                
                # Render into textbox
                editor_content = f"--- METADATA ---\nPillar: {payload.get('pillar')}\nSub-Pillar: {payload.get('sub_pillar')}\nTrend: {payload.get('trend_topic')}\nKeywords: {payload.get('keywords')}\n\n"
                editor_content += f"--- HOOKS ---\n{payload.get('hooks')}\n\n"
                editor_content += f"--- CONTENT ---\n{payload.get('content')}\n"
                
                self.after(0, lambda text=editor_content: self.update_editor_text(text))
                self.after(0, lambda: self.editor_status.configure(text="✅ Content Generated! You can edit now."))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda msg=err_msg: self.editor_status.configure(text=f"❌ Error: {msg}"))
            finally:
                self.after(0, lambda: self.btn_gen_content.configure(state="normal"))
        
        threading.Thread(target=run, daemon=True).start()

    def update_editor_text(self, text):
        self.editor_text.configure(state="normal")
        self.editor_text.delete("1.0", "end")
        self.editor_text.insert("1.0", text)

    def push_to_monday(self):
        if not self.current_editing_item or not self.current_editing_payload:
            self.editor_status.configure(text="❌ No content to push!")
            return
            
        final_text = self.editor_text.get("1.0", "end").strip()
        item = self.current_editing_item
        payload = self.current_editing_payload
        
        self.btn_push.configure(state="disabled")
        self.editor_status.configure(text="Pushing to Monday.com...")
        
        def run():
            try:
                from ai_engine import MondayAPI, MASTER_BOARD_ID, MONDAY_API_KEY
                monday_api = MondayAPI(MONDAY_API_KEY)
                
                # Column IDs from ai_engine / bulk_generator
                STATUS_COL = "status"
                PLATFORM_COL = "dropdown_mm1w7sd9"
                FORMAT_COL = "dropdown_mm1w72b4"
                PILLAR_COL = "text_mm1w3t2c"
                DESC_COL = "long_text_mm1wzgth"
                TREND_COL = "text_mm1wj52x"
                READY_CONTENT_GROUP = "group_mm1wynes"
                
                item_name = f"[{item['target_date']}] {item['title'][:50]}"
                
                final_col_values = {
                    STATUS_COL: {"label": "Ready to Publish"},
                    PLATFORM_COL: {"labels": [item["platform"]]},
                    FORMAT_COL: {"labels": [item["format"]]},
                    PILLAR_COL: payload.get("pillar", "General"),
                    DESC_COL: {"text": item.get("description", "")},
                    TREND_COL: payload.get("trend_topic", "")
                }
                final_id = monday_api.create_item(MASTER_BOARD_ID, READY_CONTENT_GROUP, item_name, column_values=json.dumps(final_col_values))
                
                formatted_body = final_text.replace("\n", "<br>")
                monday_api.post_update(final_id, f"<h2>Final Approved Content</h2><br>{formatted_body}")
                
                self.after(0, lambda: self.editor_status.configure(text="✅ Successfully pushed to Monday.com!"))
                
                # Remove from approved list
                self.approved_topics.remove(item)
                self.save_approved_topics()
                self.current_editing_item = None
                self.current_editing_payload = None
                self.after(0, self.refresh_editor_topic_list)
                self.after(0, lambda: self.editor_text.delete("1.0", "end"))
                
            except Exception as e:
                self.after(0, lambda err=e: self.editor_status.configure(text=f"❌ Error pushing: {err}"))
            finally:
                self.after(0, lambda: self.btn_push.configure(state="normal"))
                
        threading.Thread(target=run, daemon=True).start()

    def setup_bulk_tab(self):
        container = ctk.CTkFrame(self.tab_bulk, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=10)
        self.bulk_header = ctk.CTkLabel(container, text="BULK CONTENT GENERATOR (PASTE WEEKLY PLAN)", font=ctk.CTkFont(size=14, weight="bold"))
        self.bulk_header.pack(anchor="w", pady=(0, 10))
        self.split_frame = ctk.CTkFrame(container, fg_color="transparent")
        self.split_frame.pack(fill="both", expand=True)

        self.left_panel = ctk.CTkFrame(self.split_frame, fg_color="transparent")
        self.left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))
        ctk.CTkLabel(self.left_panel, text="1. Paste Raw Text Plan Here:").pack(anchor="w", pady=(0, 5))
        self.calendar_input = ctk.CTkTextbox(self.left_panel, font=("Consolas", 11), border_width=1, corner_radius=8)
        self.calendar_input.pack(fill="both", expand=True, pady=(0, 10))
        self.calendar_input.insert("1.0", "Paste your text calendar here...")
        self.btn_parse = ctk.CTkButton(self.left_panel, text="PARSE & PREVIEW", command=self.parse_calendar, fg_color="#1565c0", height=40)
        self.btn_parse.pack(fill="x")

        self.right_panel = ctk.CTkFrame(self.split_frame, fg_color="transparent")
        self.right_panel.pack(side="right", fill="both", expand=True, padx=(10, 0))
        ctk.CTkLabel(self.right_panel, text="2. Parsed Structure Preview:").pack(anchor="w", pady=(0, 5))
        self.preview_box = ctk.CTkTextbox(self.right_panel, font=("Consolas", 11), border_width=1, corner_radius=8)
        self.preview_box.pack(fill="both", expand=True, pady=(0, 10))
        self.preview_box.configure(state="normal")
        self.preview_box.insert("1.0", "Parsed items will preview here...")
        self.preview_box.configure(state="disabled")

        self.btn_run_bulk = ctk.CTkButton(self.right_panel, text="RUN BULK GENERATION", command=self.run_bulk_generation, fg_color="#2e7d32", height=40, state="disabled")
        self.btn_run_bulk.pack(fill="x")
        self.bulk_status = ctk.CTkLabel(container, text="Status: Ready", font=ctk.CTkFont(weight="bold"))
        self.bulk_status.pack(anchor="w", pady=(10, 0))

    # --- ACTIONS (BULK / LIVE) ---
    def update_log(self, text, event_type="info"):
        def append():
            self.log_view.configure(state="normal")
            self.log_view.insert("end", text + "\n\n")
            self.log_view.see("end")
            self.log_view.configure(state="disabled")
        self.after(0, append)

    def update_bulk_status(self, message, color="white"):
        def update():
            color_map = {"white": "#ffffff", "red": "#f44336", "green": "#4caf50", "orange": "#ff9800"}
            self.bulk_status.configure(text=f"Status: {message}", text_color=color_map.get(color, color))
        self.after(0, update)

    def set_preview_content(self, text):
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
        if not self.parsed_items:
            self.update_bulk_status("❌ No parsed items to generate.", "red")
            return
        self.btn_run_bulk.configure(state="disabled")
        self.btn_parse.configure(state="disabled")
        self.tabview.set("Live Feed & Controls")
        
        def run():
            from ai_engine import MondayAPI, MASTER_BOARD_ID, MONDAY_API_KEY
            client = get_gemini_client()
            monday_api = MondayAPI(MONDAY_API_KEY)
            HISTORY_GROUP = "group_mm1ws5h3"
            READY_CONTENT_GROUP = "group_mm1wynes"
            PLATFORM_COL = "dropdown_mm1w7sd9"
            FORMAT_COL = "dropdown_mm1w72b4"
            PILLAR_COL = "text_mm1w3t2c"
            DESC_COL = "long_text_mm1wzgth"
            TREND_COL = "text_mm1wj52x"
            STATUS_COL = "status"
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
                progress_msg = f"⏳ [{idx+1}/{total}] Processing: {item.get('title')} ({item.get('platform')} {item.get('format')})"
                self.update_log(progress_msg, "info")
                self.update_bulk_status(progress_msg, "orange")
                
                guideline = item.get("prompt_guideline", "")
                if not guideline:
                    fmt = item.get("format", "").lower()
                    if fmt in ["reel", "video"]: guideline = "Generate a highly dynamic short-form video script."
                    elif fmt == "carousel": guideline = "Generate a slide-by-slide outline (Slide 1 to 7)."
                    elif fmt == "poll": guideline = "Generate a caption introducing the poll."
                    elif fmt in ["article", "newsletter"]: guideline = "Write a structured long-form article."
                    else: guideline = "Write a punchy social media post."

                payload = None
                backoff = 2
                for attempt in range(1, 4):
                    try:
                        prompt = f"""
You are an elite content strategist for Infinitesol (a modern cybersecurity firm).
Determine a fitting Content Pillar, Sub-pillar, Content Angle, and Trend Topic for the following post topic:
Topic: "{item.get('title')}"
Platform: {item.get('platform')}
Format: {item.get('format')}
Description/Context: {item.get('description')}

Format-Specific Instruction: {guideline}

CRITICAL FORMATTING RULE: Do NOT use ANY markdown formatting (no hashtags # for headers, no stars * or ** for bold/italics). Output plain text formatted with standard line breaks only.

Please generate:
1. content: The full formatted post or script.
2. hooks: 5 alternative hooks
3. keywords: SEO keywords
4. competitor_insights: How legacy MSSPs fail vs Infinitesol's approach
5. engagement_score: 1-10
6. pillar: High-level content pillar
7. sub_pillar: Specific sub-pillar
8. content_angle: Content angle
9. trend_topic: Industry trend

Output a STRICT JSON response:
{{
  "pillar": "string",
  "sub_pillar": "string",
  "content_angle": "string",
  "trend_topic": "string",
  "content": "string",
  "hooks": "string",
  "keywords": "string",
  "competitor_insights": "string",
  "engagement_score": 9
}}
RAW JSON ONLY.
"""
                        response = client.models.generate_content(model=MODEL_ID, contents=prompt).text.strip()
                        if response.startswith("```json"): response = response[7:-3].strip()
                        elif response.startswith("```"): response = response[3:-3].strip()
                        payload = json.loads(response)
                        break
                    except Exception as e:
                        self.update_log(f"   ⚠️ Attempt {attempt} failed: {e}", "warning")
                        if attempt == 3: break
                        time.sleep(backoff)
                        backoff *= 2
                
                if not payload:
                    self.update_log(f"❌ Failed to generate: {item.get('title')}", "error")
                    continue
                
                try:
                    parent_name = f"📅 {item.get('day')} - {item.get('title')}"
                    parent_col_values = {
                        STATUS_COL: {"label": "Done"},
                        PLATFORM_COL: {"labels": [item.get("platform")]},
                        FORMAT_COL: {"labels": [item.get("format")]},
                        PILLAR_COL: payload.get("pillar", "General"),
                        DESC_COL: {"text": item.get("description")},
                        TREND_COL: payload.get("trend_topic", "")
                    }
                    parent_id = monday_api.create_item(MASTER_BOARD_ID, HISTORY_GROUP, parent_name, column_values=json.dumps(parent_col_values))
                    
                    sub_col_values = {
                        SUB_STATUS_COL: {"label": "Content Generated"},
                        SUB_PLATFORM_COL: {"labels": [item.get("platform")]},
                        SUB_FORMAT_COL: {"labels": [item.get("format")]},
                        SUB_PILLAR_COL: payload.get("sub_pillar", ""),
                        SUB_ANGLE_COL: payload.get("content_angle", ""),
                        SUB_TREND_COL: payload.get("trend_topic", ""),
                        SUB_DESC_COL: {"text": item.get("description")}
                    }
                    monday_api.create_item(MASTER_BOARD_ID, "", item.get("title"), parent_id=parent_id, column_values=json.dumps(sub_col_values))
                    
                    final_col_values = {
                        STATUS_COL: {"label": "Ready to Publish"},
                        PLATFORM_COL: {"labels": [item.get("platform")]},
                        FORMAT_COL: {"labels": [item.get("format")]},
                        PILLAR_COL: payload.get("pillar", "General"),
                        DESC_COL: {"text": item.get("description")},
                        TREND_COL: payload.get("trend_topic", "")
                    }
                    final_id = monday_api.create_item(MASTER_BOARD_ID, READY_CONTENT_GROUP, item.get("title"), column_values=json.dumps(final_col_values))
                    
                    content_body = (
                        f"<h2>📝 FINAL GENERATED CONTENT</h2>"
                        f"<br><b>Platform:</b> {item.get('platform')} | <b>Format:</b> {item.get('format')}"
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
                    self.update_log(f"   ✅ Successfully posted: '{item.get('title')}' (ID: {final_id})", "info")
                except Exception as ex:
                    self.update_log(f"❌ Monday.com API error for '{item.get('title')}': {ex}", "error")
                
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
