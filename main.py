import argparse
import sys
import threading
import time
import webbrowser
import uvicorn

from jarvis.config import HOST, PORT

def open_browser():
    time.sleep(1.2)
    url = f"http://{HOST}:{PORT}"
    print(f"\n[M.I.N.E] Launching HUD in default browser: {url}\n")
    webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(description="M.I.N.E. Version 1 MVP Personal Assistant")
    parser.add_argument("--cli", action="store_true", help="Launch in interactive Rich Terminal CLI mode")
    parser.add_argument("--mode", choices=["mic", "text"], default=None, help="Input mode: 'mic' (hands-free voice, primary) or 'text'")
    parser.add_argument("--mic", action="store_true", help="Force microphone voice-first mode")
    parser.add_argument("--text", action="store_true", help="Force keyboard text input mode")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    parser.add_argument("--port", type=int, default=PORT, help=f"Server port (default: {PORT})")
    args = parser.parse_args()

    if args.cli:
        mode = "text" if args.text else ("mic" if args.mic else args.mode)
        from jarvis.cli import run_cli
        run_cli(default_mode=mode)
    else:
        if not args.no_browser:
            threading.Thread(target=open_browser, daemon=True).start()

        print(f"============================================================")
        print(f"  M.I.N.E. Version 1 MVP - HUD Server Starting")
        print(f"  Interface: http://{HOST}:{args.port}")
        print(f"  Press Ctrl+C to terminate server")
        print(f"============================================================")

        uvicorn.run("jarvis.web.server:app", host=HOST, port=args.port, reload=False, log_level="info")


if __name__ == "__main__":
    main()