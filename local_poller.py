import time
import subprocess
import os
import sys
from datetime import datetime

def run_engine_command(command_args):
    """Executes a command on the ai_engine.py and returns the output."""
    try:
        # Construct the full command: python ai_engine.py [args]
        full_cmd = [sys.executable, "ai_engine.py"] + command_args
        
        # Use subprocess to run and capture output using UTF-8 to handle emojis
        result = subprocess.run(
            full_cmd, 
            capture_output=True, 
            text=True,
            encoding='utf-8',       # Explicitly read as UTF-8
            errors='replace',     # Don't crash on bad bytes
            check=False 
        )
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        output = f"[{timestamp}] [CMD: {' '.join(command_args)}]\n"
        
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\nERROR OUTPUT:\n{result.stderr}"
            
        return output
    except Exception as e:
        return f"CRITICAL SYSTEM ERROR: {str(e)}"

def start_infinite_poll(callback_fn=None):
    """
    Runs the polling loop forever (1-minute intervals).
    Optional callback_fn can be used by the GUI to update its console.
    """
    print(">>> LOCAL AUTOMATION SERVICE ACTIVE <<<")
    print("Interval: 60 seconds | Status: Running...")
    
    try:
        while True:
            # 1. Run the poll
            log_output = run_engine_command(["poll"])
            
            # 2. Inform the caller (if GUI) or print
            if callback_fn:
                callback_fn(log_output)
            else:
                print(log_output)
            
            # 3. Wait for 60 seconds
            # Split sleep into smaller chunks to allow faster exit if needed (not strictly required here)
            time.sleep(30)
    except KeyboardInterrupt:
        print("\n>>> LOCAL AUTOMATION SERVICE STOPPED <<<")

if __name__ == "__main__":
    # If run directly as a script (no GUI)
    start_infinite_poll()
