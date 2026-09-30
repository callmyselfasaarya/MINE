"""
entertainment.py — Jokes, music playback, and fun tools for M.I.N.E.
"""
import os
import random
import subprocess
import webbrowser
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.tools.registry import register_tool

logger = logging.getLogger(__name__)

# ─── Joke Database ────────────────────────────────────────────────────────────
JOKES: List[Dict[str, str]] = [
    {"setup": "Why do programmers prefer dark mode?", "punchline": "Because light attracts bugs!"},
    {"setup": "Why did the scarecrow win an award?", "punchline": "Because he was outstanding in his field!"},
    {"setup": "I told my wife she was drawing her eyebrows too high.", "punchline": "She looked surprised."},
    {"setup": "Why don't scientists trust atoms?", "punchline": "Because they make up everything!"},
    {"setup": "What do you call a fake noodle?", "punchline": "An impasta!"},
    {"setup": "Why did the bicycle fall over?", "punchline": "It was two-tired!"},
    {"setup": "What do you call cheese that isn't yours?", "punchline": "Nacho cheese!"},
    {"setup": "Why can't you give Elsa a balloon?", "punchline": "Because she'll let it go!"},
    {"setup": "I asked the librarian if they had books about paranoia.", "punchline": "She whispered: 'They're right behind you!'"},
    {"setup": "Why do cows wear bells?", "punchline": "Because their horns don't work!"},
    {"setup": "What do you call a sleeping dinosaur?", "punchline": "A dino-snore!"},
    {"setup": "Why did the math book look so sad?", "punchline": "Because it had too many problems."},
    {"setup": "What's a skeleton's least favorite room in the house?", "punchline": "The living room!"},
    {"setup": "Why don't eggs tell jokes?", "punchline": "They'd crack each other up!"},
    {"setup": "What do you call an alligator in a vest?", "punchline": "An investigator!"},
    {"setup": "Why did the golfer bring extra pants?", "punchline": "In case he got a hole in one!"},
    {"setup": "What do you call a fish without eyes?", "punchline": "A fsh!"},
    {"setup": "Why did the cookie go to the doctor?", "punchline": "Because it was feeling crummy!"},
    {"setup": "How do you organize a space party?", "punchline": "You planet!"},
    {"setup": "What do you call a boomerang that doesn't come back?", "punchline": "A stick!"},
    {"setup": "Why did the AI go to therapy?", "punchline": "It had too many deep issues!"},
    {"setup": "Why is the ocean always on time?", "punchline": "It follows the current!"},
    {"setup": "What do you call a man with no body and no nose?", "punchline": "Nobody knows!"},
    {"setup": "I'm reading a book about anti-gravity.", "punchline": "It's impossible to put down!"},
    {"setup": "Did you hear about the claustrophobic astronaut?", "punchline": "He just needed a little space!"},
    {"setup": "Why don't scientists trust atoms?", "punchline": "They make up everything!"},
    {"setup": "What did the ocean say to the beach?", "punchline": "Nothing, it just waved."},
    {"setup": "Why did the computer go to the doctor?", "punchline": "It had a virus!"},
    {"setup": "What do you call a bear with no teeth?", "punchline": "A gummy bear!"},
    {"setup": "Why do Java developers wear glasses?", "punchline": "Because they don't C#!"},
]

# ─── Common Music Directories ─────────────────────────────────────────────────
MUSIC_DIRS: List[Path] = [
    Path.home() / "Music",
    Path.home() / "Downloads",
    Path("C:/Users/Public/Music"),
]

AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"}


def _find_music_files(base_dirs: List[Path], limit: int = 200) -> List[Path]:
    """Scan music directories for audio files."""
    files: List[Path] = []
    for d in base_dirs:
        if d.exists() and d.is_dir():
            for f in d.rglob("*"):
                if f.suffix.lower() in AUDIO_EXTENSIONS and f.is_file():
                    files.append(f)
                    if len(files) >= limit:
                        return files
    return files


@register_tool(
    name="tell_joke",
    description="Tell a random joke to entertain and lighten the mood.",
    parameters={
        "category": {
            "type": "string",
            "description": "Optional joke category filter (e.g. 'tech', 'general'). Leave empty for any.",
            "required": False
        }
    }
)
def tell_joke(category: str = "") -> Dict[str, Any]:
    """Pick and return a random joke."""
    joke = random.choice(JOKES)
    full_joke = f"{joke['setup']} — {joke['punchline']}"
    return {
        "success": True,
        "setup": joke["setup"],
        "punchline": joke["punchline"],
        "full_joke": full_joke,
        "message": full_joke
    }


@register_tool(
    name="play_music",
    description=(
        "Play music on the computer. Can play a specific song/file by name, "
        "open YouTube Music, Spotify, or shuffle local music files."
    ),
    parameters={
        "query": {
            "type": "string",
            "description": (
                "Song name, artist, or keyword to play. "
                "Special values: 'spotify' opens Spotify app, "
                "'youtube' opens YouTube Music, "
                "'shuffle' or empty plays a random local music file."
            ),
            "required": False
        },
        "source": {
            "type": "string",
            "description": "Where to play from: 'local', 'youtube', 'spotify'. Default: auto-detect.",
            "required": False
        }
    }
)
def play_music(query: str = "", source: str = "") -> Dict[str, Any]:
    """Play music from various sources."""
    q = (query or "").strip().lower()
    src = (source or "").strip().lower()

    # ── Explicit source: Spotify ──
    if src == "spotify" or q in ("spotify",):
        try:
            subprocess.Popen("spotify", shell=True)
            return {"success": True, "message": "Opening Spotify for you, Sir."}
        except Exception:
            webbrowser.open("https://open.spotify.com")
            return {"success": True, "message": "Opened Spotify in your browser, Sir."}

    # ── Explicit source: YouTube Music ──
    if src == "youtube" or q in ("youtube", "youtube music"):
        url = f"https://music.youtube.com/search?q={query}" if query and q not in ("youtube", "youtube music") else "https://music.youtube.com"
        webbrowser.open(url)
        return {"success": True, "message": f"Opened YouTube Music{'  for ' + query if query else ''} in your browser, Sir."}

    # ── Search on YouTube Music if a song name is given and source is not local ──
    if query and src not in ("local",) and q not in ("shuffle", "random"):
        import urllib.parse
        search_url = f"https://music.youtube.com/search?q={urllib.parse.quote(query)}"
        webbrowser.open(search_url)
        return {
            "success": True,
            "message": f"Searching YouTube Music for '{query}', Sir.",
            "url": search_url
        }

    # ── Local shuffle / specific file ──
    music_files = _find_music_files(MUSIC_DIRS)

    if not music_files:
        # Fallback: open YouTube Music home
        webbrowser.open("https://music.youtube.com")
        return {
            "success": True,
            "message": "No local music files found. Opened YouTube Music in your browser, Sir.",
        }

    # Try to match a specific song name
    if query and q not in ("shuffle", "random", ""):
        matches = [f for f in music_files if query.lower() in f.stem.lower()]
        chosen = matches[0] if matches else random.choice(music_files)
    else:
        chosen = random.choice(music_files)

    try:
        os.startfile(str(chosen))
        return {
            "success": True,
            "message": f"Playing '{chosen.stem}' from your local library, Sir.",
            "file": str(chosen)
        }
    except Exception as e:
        return {"success": False, "error": f"Could not play local file: {str(e)}"}


@register_tool(
    name="open_website",
    description="Open any website URL in the default browser.",
    parameters={
        "url": {
            "type": "string",
            "description": "The full URL or domain to open (e.g. 'https://youtube.com' or 'github.com')",
            "required": True
        }
    }
)
def open_website(url: str) -> Dict[str, Any]:
    """Open a URL in the default web browser."""
    target = url.strip()
    if not target.startswith(("http://", "https://")):
        target = "https://" + target
    try:
        webbrowser.open(target)
        return {"success": True, "message": f"Opened {target} in your browser, Sir."}
    except Exception as e:
        return {"success": False, "error": f"Could not open website: {str(e)}"}


@register_tool(
    name="search_google",
    description="Search Google for any query and open results in the browser.",
    parameters={
        "query": {
            "type": "string",
            "description": "The search query to look up on Google",
            "required": True
        }
    }
)
def search_google(query: str) -> Dict[str, Any]:
    """Open a Google search for the given query."""
    import urllib.parse
    encoded = urllib.parse.quote(query.strip())
    url = f"https://www.google.com/search?q={encoded}"
    try:
        webbrowser.open(url)
        return {
            "success": True,
            "message": f"Opened Google search for '{query}', Sir.",
            "url": url
        }
    except Exception as e:
        return {"success": False, "error": f"Could not open Google: {str(e)}"}


@register_tool(
    name="save_note",
    description=(
        "Save an important note or text to a notes file. "
        "Appends timestamped entries to 'important_notes.txt' in the documents folder."
    ),
    parameters={
        "note": {
            "type": "string",
            "description": "The note content to save",
            "required": True
        },
        "title": {
            "type": "string",
            "description": "Optional short title or label for the note",
            "required": False
        }
    }
)
def save_note(note: str, title: str = "") -> Dict[str, Any]:
    """Append a timestamped note to the important notes file."""
    from datetime import datetime
    from jarvis.config import DOCUMENTS_DIR

    notes_file = DOCUMENTS_DIR / "important_notes.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    heading = f"[{title.upper()}] " if title else ""
    entry = f"\n{'=' * 50}\n{heading}{timestamp}\n{note.strip()}\n"

    try:
        with open(notes_file, "a", encoding="utf-8") as f:
            f.write(entry)
        return {
            "success": True,
            "message": f"Note saved successfully to 'important_notes.txt', Sir.",
            "path": str(notes_file),
            "entry": entry.strip()
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to save note: {str(e)}"}


@register_tool(
    name="greet_user",
    description="Greet the user with a time-aware personalized message.",
    parameters={}
)
def greet_user() -> Dict[str, Any]:
    """Return a context-aware greeting."""
    from datetime import datetime
    from jarvis.config import USER_NAME, ASSISTANT_NAME

    now = datetime.now()
    hour = now.hour
    if 5 <= hour < 12:
        period = "morning"
    elif 12 <= hour < 17:
        period = "afternoon"
    elif 17 <= hour < 21:
        period = "evening"
    else:
        period = "night"

    greeting = (
        f"Good {period}, {USER_NAME}! I am {ASSISTANT_NAME}, your personal assistant, "
        f"fully online and ready to serve. Today is {now.strftime('%A, %B %d, %Y')} "
        f"and the time is {now.strftime('%I:%M %p')}. How may I assist you?"
    )
    return {"success": True, "message": greeting, "period": period}