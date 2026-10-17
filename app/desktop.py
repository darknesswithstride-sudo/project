"""Optional desktop shell for the local OmniForge web application.

Install requirements-desktop.txt for a native WebView window. Without pywebview,
this opens the same local UI in the default browser. No network exposure is used.
"""
import threading
import time
import webbrowser

HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"


def _serve():
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, log_level="warning")


def main():
    import urllib.request
    try:
        with urllib.request.urlopen(URL + "/api/status", timeout=0.5):
            already_running = True
    except Exception:
        already_running = False
    if not already_running:
        threading.Thread(target=_serve, daemon=True).start()
        for _ in range(80):
            try:
                with urllib.request.urlopen(URL + "/api/status", timeout=0.5):
                    break
            except Exception:
                time.sleep(0.25)
        else:
            raise RuntimeError("OmniForge server did not start. Check Python dependencies and port 8000.")
    try:
        import webview
        webview.create_window("OmniForge AI — Free Local Edition", URL, width=1440, height=920, min_size=(980, 650))
        webview.start()
    except ImportError:
        webbrowser.open(URL)
        print("OmniForge is running at", URL)
        print("Close this terminal to stop the local server. For a native window, install requirements-desktop.txt.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
