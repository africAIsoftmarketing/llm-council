"""
LLM Council Launcher - Python/Tkinter GUI
A lightweight launcher application for LLM Council
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import threading
import webbrowser
import os
import sys
import json
import signal
from pathlib import Path

# Application paths
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    APP_DIR = Path(sys.executable).parent
else:
    # Running as script
    APP_DIR = Path(__file__).parent.parent

PYTHON_DIR = APP_DIR / "python"
BACKEND_DIR = APP_DIR / "backend"
DATA_DIR = APP_DIR / "data"
CONFIG_FILE = DATA_DIR / "config.json"

# Find Python executable
if (PYTHON_DIR / "python.exe").exists():
    PYTHON_EXE = str(PYTHON_DIR / "python.exe")
else:
    PYTHON_EXE = sys.executable


class LLMCouncilLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("LLM Council")
        self.root.geometry("500x400")
        self.root.resizable(False, False)
        
        # Set icon if available
        icon_path = APP_DIR / "assets" / "icon.ico"
        if icon_path.exists():
            self.root.iconbitmap(str(icon_path))
        
        # Backend process
        self.backend_process = None
        self.is_running = False
        
        # Load configuration
        self.config = self.load_config()
        
        # Create UI
        self.create_ui()
        
        # Check initial status
        self.check_status()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def load_config(self):
        """Load configuration from file."""
        default_config = {
            "backend_port": 8001,
            "frontend_port": 3000,
            "auto_start": False,
            "minimize_to_tray": True,
            "openrouter_api_key": ""
        }
        
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    return {**default_config, **config}
            except:
                pass
        
        return default_config
    
    def save_config(self):
        """Save configuration to file."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def create_ui(self):
        """Create the main UI."""
        # Main frame with padding
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(
            main_frame, 
            text="LLM Council",
            font=("Segoe UI", 24, "bold")
        )
        title_label.pack(pady=(0, 5))
        
        subtitle_label = ttk.Label(
            main_frame,
            text="Multi-LLM Deliberation System",
            font=("Segoe UI", 10)
        )
        subtitle_label.pack(pady=(0, 20))
        
        # Status indicator
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=10)
        
        self.status_canvas = tk.Canvas(status_frame, width=16, height=16, highlightthickness=0)
        self.status_canvas.pack(side=tk.LEFT, padx=(0, 10))
        self.status_indicator = self.status_canvas.create_oval(2, 2, 14, 14, fill="gray")
        
        self.status_label = ttk.Label(status_frame, text="Status: Unknown", font=("Segoe UI", 10))
        self.status_label.pack(side=tk.LEFT)
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=20)
        
        # Start/Stop button
        self.start_stop_btn = ttk.Button(
            buttons_frame,
            text="Start Server",
            command=self.toggle_server,
            width=20
        )
        self.start_stop_btn.pack(pady=5)
        
        # Open Dashboard button
        self.open_btn = ttk.Button(
            buttons_frame,
            text="Open Dashboard",
            command=self.open_dashboard,
            width=20
        )
        self.open_btn.pack(pady=5)
        
        # Settings button
        settings_btn = ttk.Button(
            buttons_frame,
            text="Settings",
            command=self.open_settings,
            width=20
        )
        settings_btn.pack(pady=5)
        
        # Separator
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)
        
        # Quick links
        links_frame = ttk.Frame(main_frame)
        links_frame.pack(fill=tk.X)
        
        ttk.Label(links_frame, text="Quick Links:", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        
        link1 = ttk.Label(links_frame, text="• Get OpenRouter API Key", foreground="blue", cursor="hand2")
        link1.pack(anchor=tk.W, padx=(10, 0))
        link1.bind("<Button-1>", lambda e: webbrowser.open("https://openrouter.ai/keys"))
        
        link2 = ttk.Label(links_frame, text="• Documentation", foreground="blue", cursor="hand2")
        link2.pack(anchor=tk.W, padx=(10, 0))
        link2.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/karpathy/llm-council"))
        
        # Version info
        version_label = ttk.Label(
            main_frame,
            text="Version 2.0.0",
            font=("Segoe UI", 8),
            foreground="gray"
        )
        version_label.pack(side=tk.BOTTOM, pady=(20, 0))
    
    def check_status(self):
        """Check if the backend is running."""
        import urllib.request
        import urllib.error
        
        try:
            port = self.config.get("backend_port", 8001)
            req = urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
            if req.status == 200:
                self.set_status(True)
            else:
                self.set_status(False)
        except:
            self.set_status(False)
        
        # Check again in 5 seconds
        self.root.after(5000, self.check_status)
    
    def set_status(self, running):
        """Update the status indicator."""
        self.is_running = running
        
        if running:
            self.status_canvas.itemconfig(self.status_indicator, fill="#27ae60")
            self.status_label.config(text="Status: Running")
            self.start_stop_btn.config(text="Stop Server")
            self.open_btn.config(state=tk.NORMAL)
        else:
            self.status_canvas.itemconfig(self.status_indicator, fill="#e74c3c")
            self.status_label.config(text="Status: Stopped")
            self.start_stop_btn.config(text="Start Server")
    
    def toggle_server(self):
        """Start or stop the server."""
        if self.is_running:
            self.stop_server()
        else:
            self.start_server()
    
    def start_server(self):
        """Start the backend server."""
        self.status_label.config(text="Status: Starting...")
        self.start_stop_btn.config(state=tk.DISABLED)
        
        def run_server():
            try:
                # Ensure data directories exist
                (DATA_DIR / "conversations").mkdir(parents=True, exist_ok=True)
                (DATA_DIR / "documents").mkdir(parents=True, exist_ok=True)
                
                # Set environment
                env = os.environ.copy()
                env["DATA_DIR"] = str(DATA_DIR)
                env["PYTHONPATH"] = str(BACKEND_DIR)
                
                port = self.config.get("backend_port", 8001)
                
                # Start uvicorn
                self.backend_process = subprocess.Popen(
                    [
                        PYTHON_EXE, "-m", "uvicorn",
                        "main:app",
                        "--host", "0.0.0.0",
                        "--port", str(port)
                    ],
                    cwd=str(BACKEND_DIR),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                
                # Wait a bit and check if started
                import time
                time.sleep(3)
                
                self.root.after(0, lambda: self.start_stop_btn.config(state=tk.NORMAL))
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(
                    "Error",
                    f"Failed to start server: {str(e)}"
                ))
                self.root.after(0, lambda: self.start_stop_btn.config(state=tk.NORMAL))
        
        threading.Thread(target=run_server, daemon=True).start()
    
    def stop_server(self):
        """Stop the backend server."""
        self.status_label.config(text="Status: Stopping...")
        
        if self.backend_process:
            try:
                if sys.platform == 'win32':
                    self.backend_process.terminate()
                else:
                    os.killpg(os.getpgid(self.backend_process.pid), signal.SIGTERM)
                self.backend_process = None
            except:
                pass
        
        # Also try to kill any process on the port
        port = self.config.get("backend_port", 8001)
        if sys.platform == 'win32':
            os.system(f'for /f "tokens=5" %a in (\'netstat -aon ^| findstr :{port} ^| findstr LISTENING\') do taskkill /F /PID %a >nul 2>&1')
    
    def open_dashboard(self):
        """Open the web dashboard in the default browser."""
        port = self.config.get("backend_port", 8001)
        webbrowser.open(f"http://localhost:3000")
    
    def open_settings(self):
        """Open settings dialog."""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Settings")
        settings_window.geometry("400x300")
        settings_window.resizable(False, False)
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        frame = ttk.Frame(settings_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Backend port
        ttk.Label(frame, text="Backend Port:").grid(row=0, column=0, sticky=tk.W, pady=5)
        port_var = tk.StringVar(value=str(self.config.get("backend_port", 8001)))
        port_entry = ttk.Entry(frame, textvariable=port_var, width=10)
        port_entry.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # Auto start
        auto_start_var = tk.BooleanVar(value=self.config.get("auto_start", False))
        auto_start_cb = ttk.Checkbutton(
            frame,
            text="Start server automatically on launch",
            variable=auto_start_var
        )
        auto_start_cb.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Data directory
        ttk.Label(frame, text="Data Directory:").grid(row=2, column=0, sticky=tk.W, pady=5)
        data_dir_label = ttk.Label(frame, text=str(DATA_DIR), foreground="gray")
        data_dir_label.grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # Open data folder button
        def open_data_folder():
            if sys.platform == 'win32':
                os.startfile(str(DATA_DIR))
            else:
                webbrowser.open(f"file://{DATA_DIR}")
        
        open_folder_btn = ttk.Button(frame, text="Open Folder", command=open_data_folder)
        open_folder_btn.grid(row=3, column=0, columnspan=2, pady=10)
        
        # Save button
        def save_settings():
            try:
                self.config["backend_port"] = int(port_var.get())
                self.config["auto_start"] = auto_start_var.get()
                self.save_config()
                messagebox.showinfo("Settings", "Settings saved successfully!")
                settings_window.destroy()
            except ValueError:
                messagebox.showerror("Error", "Invalid port number")
        
        save_btn = ttk.Button(frame, text="Save", command=save_settings)
        save_btn.grid(row=4, column=0, columnspan=2, pady=20)
    
    def on_close(self):
        """Handle window close."""
        if self.is_running:
            if messagebox.askyesno(
                "Quit",
                "The server is still running. Do you want to stop it and quit?"
            ):
                self.stop_server()
                self.root.destroy()
        else:
            self.root.destroy()


def main():
    root = tk.Tk()
    
    # Apply a modern theme if available
    try:
        root.tk.call("source", "azure.tcl")
        root.tk.call("set_theme", "light")
    except:
        pass
    
    app = LLMCouncilLauncher(root)
    
    # Auto-start if configured
    if app.config.get("auto_start", False):
        root.after(1000, app.start_server)
    
    root.mainloop()


if __name__ == "__main__":
    main()
