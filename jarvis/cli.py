import sys
import threading
import time
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt

try:
    import msvcrt
except ImportError:
    msvcrt = None

from jarvis.config import (
    ASSISTANT_NAME,
    USER_NAME,
    WAKE_WORD,
    WAKE_WORD_ENABLED,
    WAKE_WORD_ALIASES,
    PRIMARY_INPUT_MODE,
)
from jarvis.core.agent import jarvis_agent
from jarvis.voice.stt import listen, calibrate, stt
from jarvis.voice.tts import speak
from jarvis.voice.wake_word import wake_engine

console = Console()

BANNER = f"""[bold cyan]
███╗   ███╗██╗███╗   ██╗███████╗
████╗ ████║██║████╗  ██║██╔════╝
██╔████╔██║██║██╔██╗ ██║█████╗  
██║╚██╔╝██║██║██║╚██╗██║██╔══╝  
██║ ╚═╝ ██║██║██║ ╚████║███████╗
╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚══════╝
[/bold cyan]
[dim cyan]M.I.N.E. Version 1 MVP • Personal Desktop AI Assistant[/dim cyan]
"""


def _handle_interaction(user_text: str) -> None:
    """Run a full interact cycle and print the result to console."""
    wake_engine.pause()
    try:
        result = jarvis_agent.interact(user_text, speak_output=True)

        if result.get("tool_called"):
            console.print(
                f"[bold yellow]⚙️ Tool:[/bold yellow] [bold]{result.get('tool_called')}[/bold]"
                + (f"  [dim]{result.get('tool_args')}[/dim]" if result.get("tool_args") else "")
            )

        response_text = result.get("text", "")
        if response_text:
            console.print(Panel(
                Text(response_text, style="bold white"),
                title=f"[bold cyan]{ASSISTANT_NAME}[/bold cyan]",
                border_style="cyan"
            ))
    finally:
        wake_engine.resume()


def _on_wake_detected(utterance: str) -> None:
    """
    Called by the wake-word engine when the wake phrase is heard.
    Plays an acknowledgement tone, then listens for the actual command.
    """
    console.print(
        f"\n[bold green]🎙️  Wake word detected![/bold green] "
        f"[dim](heard: \"{utterance}\")[/dim]"
    )
    speak("Yes?")

    console.print("[bold green]🎙️  Listening for your command...[/bold green]")
    command = listen(timeout=7.0, phrase_time_limit=15.0)

    if not command or not command.strip():
        console.print("[dim yellow]No command heard after wake word.[/dim yellow]")
        wake_engine.resume()
        return

    console.print(f"[bold cyan]{USER_NAME} (Voice):[/bold cyan] {command}")
    _handle_interaction(command)


def _toggle_wake_word(enable: bool) -> None:
    """Start or stop the wake-word engine and print status."""
    if enable:
        if wake_engine.is_running:
            console.print(
                f"[dim yellow]Wake-word detection is already active. "
                f"Listening for [bold]\"{wake_engine.wake_word}\"[/bold].[/dim yellow]"
            )
            return
        wake_engine.on_wake(_on_wake_detected)
        ok = wake_engine.start()
        if ok:
            all_triggers = [wake_engine.wake_word] + wake_engine.aliases
            triggers_str = " / ".join(f'"{t}"' for t in all_triggers)
            console.print(Panel(
                f"[bold green]✅ Wake-word mode ENABLED[/bold green]\n\n"
                f"Say {triggers_str} to activate the assistant.\n"
                f"[dim]The assistant will acknowledge with \"Yes?\" then listen for your command.[/dim]\n\n"
                f"[dim]Type [bold]/wake off[/bold] to disable.[/dim]",
                border_style="green",
                title="[bold green]Wake Word Active[/bold green]"
            ))
            speak(f"Wake word mode enabled. Say {wake_engine.wake_word} to activate me.")
        else:
            console.print("[bold red]❌ Could not start wake-word detection. Is your microphone connected?[/bold red]")
    else:
        if not wake_engine.is_running:
            console.print("[dim yellow]Wake-word detection is already off.[/dim yellow]")
            return
        wake_engine.stop()
        console.print(Panel(
            "[bold red]🔇 Wake-word mode DISABLED[/bold red]\n\n"
            "[dim]Type [bold]/wake[/bold] or [bold]/wake on[/bold] to re-enable.[/dim]",
            border_style="red",
            title="[bold red]Wake Word Off[/bold red]"
        ))
        speak("Wake word mode disabled.")


def run_cli(default_mode: Optional[str] = None):
    console.print(BANNER)

    # Determine mode: default to PRIMARY_INPUT_MODE ('mic' by default)
    mode = (default_mode or PRIMARY_INPUT_MODE or "mic").lower().strip()
    if mode in ("voice", "microphone"):
        mode = "mic"
    if mode not in ("mic", "text"):
        mode = "mic"

    all_triggers = [WAKE_WORD] + WAKE_WORD_ALIASES
    triggers_str = " / ".join(f'"{t}"' for t in all_triggers)

    mode_label = "🎙️ Microphone (Hands-Free Voice Active)" if mode == "mic" else "⌨️ Keyboard Text Active"
    console.print(
        f"[dim]Primary Input Mode: [/dim][bold green]{mode_label}[/bold green]\n"
        f"[dim]Commands: "
        f"[bold]/mic[/bold] switch to voice  •  "
        f"[bold]/text[/bold] switch to typing  •  "
        f"[bold]/wake[/bold] toggle wake-word ({triggers_str})  •  "
        f"[bold]/exit[/bold] quit[/dim]\n"
    )

    # Time-aware greeting on startup
    from jarvis.tools.entertainment import greet_user
    greeting_data = greet_user()
    greeting_msg = greeting_data.get(
        "message", f"Greetings, {USER_NAME}. {ASSISTANT_NAME} is online and standing by."
    )
    console.print(Panel(
        Text(greeting_msg, style="bold white"),
        title=f"[bold cyan]{ASSISTANT_NAME}[/bold cyan]",
        border_style="cyan"
    ))

    # Pre-calibrate microphone in background while greeting
    cal_thread = threading.Thread(target=calibrate, args=(0.3,), daemon=True)
    cal_thread.start()

    speak(greeting_msg)
    cal_thread.join(timeout=1.0)

    # Register wake word callback
    wake_engine.on_wake(_on_wake_detected)

    if mode == "mic":
        wake_engine.pause()
        console.print(Panel(
            f"[bold green]🎙️ MIC MODE ACTIVE (PRIMARY)[/bold green]\n\n"
            f"• {ASSISTANT_NAME} is listening automatically for your voice.\n"
            f"• Speak your requests freely into your microphone.\n"
            f"• Say [bold]\"switch to text\"[/bold] or press [bold][Enter][/bold] to switch to Keyboard Text Mode.\n"
            f"• Say [bold]\"quit\"[/bold] or [bold]\"exit\"[/bold] to shut down.",
            title="[bold green]Hands-Free Voice Communication[/bold green]",
            border_style="green"
        ))
    else:
        if WAKE_WORD_ENABLED:
            _toggle_wake_word(True)

    silence_count = 0

    while True:
        try:
            # Show confirmation prompt if a dangerous action is pending
            pending = jarvis_agent.guardrails.get_pending_action()
            if pending:
                console.print(Panel(
                    f"[bold yellow]⚠️ AUTHORIZATION REQUIRED[/bold yellow]\n"
                    f"{pending.prompt_message}\n\n"
                    f"[dim]Say or type 'yes' / 'confirm' to authorize, or 'no' / 'cancel' to abort.[/dim]",
                    border_style="yellow"
                ))

            # ── PRIMARY MIC MODE ───────────────────────────────────────────────
            if mode == "mic":
                # Check if user pressed a key on keyboard to switch to text mode
                if msvcrt and msvcrt.kbhit():
                    while msvcrt.kbhit():
                        msvcrt.getch()
                    mode = "text"
                    console.print("\n[bold yellow]⌨️ Switched to Keyboard Text Mode.[/bold yellow] [dim](Type /mic to return to Voice Mode)[/dim]")
                    continue

                if silence_count == 0:
                    console.print(f"[bold green]🎙️ Listening to {USER_NAME}...[/bold green] [dim](Speak now or press Enter for text)[/dim]")

                heard = listen(timeout=5.5, phrase_time_limit=15.0)

                # Check again if key was pressed during listening
                if msvcrt and msvcrt.kbhit():
                    while msvcrt.kbhit():
                        msvcrt.getch()
                    mode = "text"
                    console.print("\n[bold yellow]⌨️ Switched to Keyboard Text Mode.[/bold yellow] [dim](Type /mic to return to Voice Mode)[/dim]")
                    continue

                if not heard or not heard.strip():
                    if stt.last_error:
                        console.print(f"[bold red]⚠️ {stt.last_error}[/bold red]")
                    silence_count += 1
                    if silence_count % 4 == 0:
                        console.print(f"[dim]🎙️ Still listening for {USER_NAME}... (or press Enter to type)[/dim]")
                    continue

                silence_count = 0
                clean = heard.strip()
                lower = clean.lower()
                console.print(f"[bold cyan]{USER_NAME} (Voice):[/bold cyan] {clean}")

                # Voice exit command
                if lower in ("/exit", "exit", "quit", "q", "goodbye", "bye", "shut down", "stop session", "terminate"):
                    console.print(f"[bold red]Shutting down {ASSISTANT_NAME} session. Goodbye, {USER_NAME}.[/bold red]")
                    speak(f"Shutting down session. Goodbye, {USER_NAME}.")
                    break

                # Voice mode toggle
                if lower in ("switch to text", "text mode", "keyboard mode", "type mode", "switch to typing"):
                    console.print("[bold yellow]⌨️ Switched to Keyboard Text Mode.[/bold yellow] [dim](Type /mic to return to Voice Mode)[/dim]")
                    speak("Switched to text mode. You can type your commands now.")
                    mode = "text"
                    continue

                # Voice authorization
                if pending:
                    if any(w in lower for w in ("yes", "confirm", "proceed", "authorize", "do it")):
                        jarvis_agent.confirm_action()
                        continue
                    elif any(w in lower for w in ("no", "cancel", "abort", "don't", "stop")):
                        jarvis_agent.cancel_action()
                        continue

                # Normal voice interaction
                _handle_interaction(clean)
                continue

            # ── KEYBOARD TEXT MODE ─────────────────────────────────────────────
            user_input = Prompt.ask(f"[bold cyan]{USER_NAME}[/bold cyan]")
            if not user_input.strip():
                continue

            clean = user_input.strip()
            lower = clean.lower()

            if lower in ("/exit", "exit", "quit", "q"):
                if wake_engine.is_running:
                    wake_engine.stop()
                console.print(f"[bold red]Shutting down {ASSISTANT_NAME} session. Goodbye, {USER_NAME}.[/bold red]")
                speak(f"Shutting down session. Goodbye, {USER_NAME}.")
                break

            if lower in ("/mic", "mic", "/voice", "voice"):
                mode = "mic"
                wake_engine.pause()
                silence_count = 0
                console.print("[bold green]🎙️ Switched to Mic Mode (Primary). Listening actively...[/bold green]")
                speak("Mic mode active. I am listening.")
                continue

            if lower.startswith("/mic list") or lower.startswith("/mic devices"):
                mics = stt.get_microphones()
                table = Table(title="[bold cyan]Available Audio Input Devices[/bold cyan]", border_style="cyan")
                table.add_column("Index", style="bold yellow", justify="center")
                table.add_column("Device Name", style="bold white")
                table.add_column("Status", style="green")
                active_idx = stt.device_index
                for m in mics:
                    is_active = (active_idx == m["index"]) or (active_idx is None and m["index"] == 0)
                    status = "[bold green]ACTIVE[/bold green]" if is_active else "[dim]Available[/dim]"
                    table.add_row(str(m["index"]), m["name"], status)
                console.print(table)
                console.print("[dim]Use [bold]/mic set <index>[/bold] to select a different microphone.[/dim]")
                continue

            if lower.startswith("/mic set"):
                parts = lower.split(maxsplit=2)
                if len(parts) >= 3 and parts[2].strip().isdigit():
                    new_idx = int(parts[2].strip())
                    stt.set_device_index(new_idx)
                    console.print(f"[bold green]Microphone device updated to index {new_idx}.[/bold green]")
                else:
                    console.print("[dim yellow]Usage: /mic set <device_index>[/dim yellow]")
                continue

            if lower in ("/text", "text"):
                console.print("[dim yellow]Already in text mode.[/dim yellow]")
                continue

            if lower in ("/mode", "mode"):
                mode = "mic" if mode == "text" else "text"
                console.print(f"[bold cyan]Input mode switched to: {mode.upper()}[/bold cyan]")
                continue

            if lower.startswith("/wake"):
                parts = lower.split(maxsplit=1)
                sub = parts[1].strip() if len(parts) > 1 else ""

                if sub.startswith("set "):
                    new_word = sub[4:].strip()
                    if new_word:
                        wake_engine.set_wake_word(new_word)
                        console.print(f"[bold cyan]Wake word updated to:[/bold cyan] \"{new_word}\"")
                    else:
                        console.print("[dim]Usage: /wake set <phrase>[/dim]")
                elif sub in ("off", "disable", "stop"):
                    _toggle_wake_word(False)
                else:
                    _toggle_wake_word(not wake_engine.is_running)
                continue

            # Normal text interaction
            _handle_interaction(clean)

        except (KeyboardInterrupt, EOFError):
            if wake_engine.is_running:
                wake_engine.stop()
            console.print(f"\n[bold red]Terminating {ASSISTANT_NAME} CLI...[/bold red]")
            break
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")


if __name__ == "__main__":
    run_cli()