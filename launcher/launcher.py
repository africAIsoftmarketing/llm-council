"""
LLM Council Launcher
Starts the backend server and opens the web UI.
Sits in the system tray with Stop option.
"""
import sys
import os
import subprocess
import threading
import time
import webbrowser
import urllib.request

# Determine app directory (works both frozen PyInstaller and dev)
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

PYTHON_EXE  = os.path.join(APP_DIR, 'python', 'python.exe')
BACKEND_DIR = os.path.join(APP_DIR, 'backend')
PORT        = 8001
URL         = f'http://localhost:{PORT}'
HEALTH_URL  = f'{URL}/api/health'


def is_server_running() -> bool:
    """Check if the backend server is responding."""
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def start_backend():
    """Start uvicorn backend as a hidden subprocess."""
    env = os.environ.copy()
    env['PYTHONPATH'] = BACKEND_DIR

    # Use embedded Python if available, otherwise system Python
    python = PYTHON_EXE if os.path.exists(PYTHON_EXE) else sys.executable

    cmd = [
        python, '-m', 'uvicorn', 'main:app',
        '--host', '127.0.0.1',
        '--port', str(PORT),
        '--log-level', 'error'
    ]

    creationflags = 0
    if sys.platform == 'win32':
        creationflags = subprocess.CREATE_NO_WINDOW

    proc = subprocess.Popen(
        cmd,
        cwd=BACKEND_DIR,
        env=env,
        creationflags=creationflags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    return proc


def wait_for_server(timeout: int = 30) -> bool:
    """Poll until server is ready or timeout."""
    for _ in range(timeout):
        if is_server_running():
            return True
        time.sleep(1)
    return False


def run_with_tray(backend_proc):
    """Run with system tray icon (requires pystray + Pillow)."""
    try:
        import pystray
        from PIL import Image, ImageDraw

        # Create simple icon (blue circle) if no icon.ico
        icon_path = os.path.join(APP_DIR, 'icon.ico')
        if os.path.exists(icon_path):
            img = Image.open(icon_path)
        else:
            img = Image.new('RGB', (64, 64), color='#4a90e2')
            draw = ImageDraw.Draw(img)
            draw.ellipse([8, 8, 56, 56], fill='white')

        def open_browser(icon, item):
            webbrowser.open(URL)

        def stop_server(icon, item):
            icon.stop()
            backend_proc.terminate()
            sys.exit(0)

        menu = pystray.Menu(
            pystray.MenuItem('Ouvrir LLM Council', open_browser, default=True),
            pystray.MenuItem('Arrêter le serveur', stop_server),
        )

        tray = pystray.Icon('LLM Council', img, 'LLM Council', menu)
        tray.run()

    except ImportError:
        # No systray support - just wait for process
        try:
            backend_proc.wait()
        except KeyboardInterrupt:
            backend_proc.terminate()


def show_error(message: str):
    """Show error message using tkinter messagebox."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror('LLM Council', message)
        root.destroy()
    except Exception:
        print(f"ERROR: {message}")


def main():
    # If already running, just open browser
    if is_server_running():
        webbrowser.open(URL)
        return

    # Start backend
    proc = start_backend()

    # Wait for ready
    ready = wait_for_server(timeout=30)
    if not ready:
        show_error(
            f'Le serveur n\'a pas démarré dans les 30 secondes.\n'
            f'Vérifiez que le port {PORT} est disponible.'
        )
        proc.terminate()
        sys.exit(1)

    # Open browser
    webbrowser.open(URL)

    # Stay in tray
    run_with_tray(proc)


if __name__ == '__main__':
    main()
