import argparse
import time
import os
import sys
import subprocess
import psutil
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True, help="PID of the process to wait for")
    parser.add_argument("--script", type=str, required=True, help="Path to the run script to execute")
    parser.add_argument("--update", action="store_true", help="Perform git pull and pip install")
    args = parser.parse_args()

    # 1. Wait for the parent process to exit
    print(f"[Updater] Waiting for process {args.pid} to terminate...")
    try:
        proc = psutil.Process(args.pid)
        proc.wait(timeout=30)
    except psutil.NoSuchProcess:
        print("[Updater] Process already terminated.")
    except psutil.TimeoutExpired:
        print("[Updater] Process did not terminate in time. Forcing kill...")
        try:
            proc.kill()
        except:
            pass

    # Give OS a moment to release file locks
    time.sleep(2)

    # 2. Update if requested
    if args.update:
        print("[Updater] Starting update process...")
        try:
            print("[Updater] Pulling latest code...")
            subprocess.check_call(["git", "pull"])
            
            print("[Updater] Installing dependencies...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-cache-dir", "-r", "requirements.txt"])
            
            print("[Updater] Update complete.")
        except Exception as e:
            print(f"[Updater] CRITICAL: Update failed: {e}")
            print("[Updater] Attempting to restart application anyway...")
            time.sleep(2)

    # 3. Restart the Application
    script_path = Path(args.script).resolve()
    print(f"[Updater] Relaunching application via: {script_path}")
    
    try:
        if os.name == 'nt':
            # Windows: Open in a new console window so the user can see logs
            subprocess.Popen([str(script_path)], creationflags=subprocess.CREATE_NEW_CONSOLE, shell=True)
        else:
            # Linux/Mac: Detach process
            subprocess.Popen(['bash', str(script_path)], start_new_session=True)
            
        print("[Updater] Launch command issued. Exiting updater.")
        sys.exit(0)
    except Exception as e:
        print(f"[Updater] Failed to restart application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
