import customtkinter as ctk
import threading
import sys
import os
import time
from datetime import datetime
from local_poller import run_engine_command

# --- CONFIGURATION ---
POLL_INTERVAL_S = 60  # User requested polling every minute

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
            # Execute one poll cycle
            output = run_engine_command(["poll"])
            self.log_callback(output, "poll_result")
            
            # Wait for interval, but check flag frequently for immediate stop
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
    """Modern UI for the AI Content Factory Management."""
    def __init__(self):
        super().__init__()

        # --- Basic Window Setup ---
        self.title("Infinitesol AI Content Matrix | Local Control Center")
        self.geometry("900x700")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.manager = AutomationManager(self.update_log)

        # --- Sidebar (Navigation & Controls) ---
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        self.brand_label = ctk.CTkLabel(self.sidebar, text="INFINITESOL", 
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

        # --- Main Workspace (Logs) ---
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(side="right", fill="both", expand=True, padx=20, pady=20)

        self.header = ctk.CTkLabel(self.container, text="AUTOMATION ENGINE LIVE FEED", 
                                   font=ctk.CTkFont(size=14, weight="bold"))
        self.header.pack(anchor="w", pady=(0, 15))

        self.log_view = ctk.CTkTextbox(self.container, font=("Consolas", 12), border_width=0, corner_radius=10)
        self.log_view.pack(fill="both", expand=True)
        self.log_view.configure(state="normal")
        self.log_view.insert("0.0", f"[{datetime.now().strftime('%H:%M:%S')}] Application Initialization Complete.\nWaiting for user interaction...\n" + "—"*60 + "\n\n")
        self.log_view.configure(state="disabled")

    # --- ACTIONS ---
    def update_log(self, text, event_type="info"):
        """Thread-safe update of the log window."""
        def append():
            self.log_view.configure(state="normal")
            self.log_view.insert("end", text + "\n\n")
            self.log_view.see("end")
            self.log_view.configure(state="disabled")
        
        self.after(0, append)

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
        # Run in thread to avoid freezing UI
        threading.Thread(target=self.manager.manual_recommend, daemon=True).start()

    def shutdown(self):
        self.manager.stop_polling()
        self.destroy()
        sys.exit(0)

if __name__ == "__main__":
    app = DashboardGUI()
    # Ensure graceful exit on window close
    app.protocol("WM_DELETE_WINDOW", app.shutdown)
    app.mainloop()
