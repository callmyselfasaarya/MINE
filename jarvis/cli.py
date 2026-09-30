import sys
import threading
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt
from rich.live import Live
from rich.spinner import Spinner

from jarvis.config import ASSISTANT_NAME, USER_NAME, WAKE_WORD, WAKE_WORD_ENABLED, WAKE_WORD_ALIASES
from jarvis.core.agent import jarvis_agent
from jarvis.voice.stt import listen
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


def print_status_table():
    state = jarvis_agent.get_dashboard_state()
    table = Table(title="[bold cyan]System State[/bold cyan]", border_style="cyan")
    table.add_column("Module", style="bold white")
    table.add_column("Status / Count", style="green")

    ai_mode = state.get("active_label", "Local Intent Engine (Active)")
    table.add_row("🧠 AI Brain", ai_mode)

    sys_info = state.get("system_status", {})
    cpu = sys_info.get("cpu_usage_percent", "N/A")
    ram = sys_info.get("ram_usage_percent", "N/A")
    table.add_row("🖥️ Hardware", f"CPU: {cpu}% | RAM: {ram}%")

    table.add_row("⏰ Reminders", f"{len(state.get('reminders', []))} pending")
    table.add_row("📅 Calendar", f"{len(state.get('calendar_events', []))} events")
    table.add_row("🧠 Long-Term Memory", f"{len(state.get('memories', []))} facts remembered")
    table.add_row("📁 Documents", f"{len(state.get('documents', []))} files")

    # Show wake-word status
    wake_status = (
        f"[bold green]ACTIVE[/bold green] — listening for [bold cyan]\"{wake_engine.wake_word}\"[/bold cyan]"
        if wake_engine.is_running
        else "[dim]OFF[/dim]"
    )
    table.add_row("🎙️ Wake Word", wake_status)

    console.print(table)


def _handle_interaction(user_text: str) -> None:
    """Run a full interact cycle and print the result to console."""
    # Pause wake-word detection while we process + respond
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
        # Always resume detection after handling, even if an error occurred
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

    # Listen for the actual command (longer timeout for command)
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


def run_cli():
    console.print(BANNER)
    print_status_table()

    all_triggers = [WAKE_WORD] + WAKE_WORD_ALIASES
    triggers_str = " / ".join(f'"{t}"' for t in all_triggers)
    console.print(
        f"\n[dim]Commands: "
        f"[bold]/mic[/bold] listen once  •  "
        f"[bold]/wake[/bold] toggle wake-word ({triggers_str})  •  "
        f"[bold]/status[/bold] vitals  •  "
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
    speak(greeting_msg)

    # Auto-start wake-word if enabled in .env
    if WAKE_WORD_ENABLED:
        _toggle_wake_word(True)

    while True:
        try:
            # Show confirmation prompt if a dangerous action is pending
            pending = jarvis_agent.guardrails.get_pending_action()
            if pending:
                console.print(Panel(
                    f"[bold yellow]⚠️ AUTHORIZATION REQUIRED[/bold yellow]\n"
                    f"{pending.prompt_message}\n\n"
                    f"[dim]Type 'yes' / 'confirm' to authorize, or 'no' / 'cancel' to abort.[/dim]",
                    border_style="yellow"
                ))

            user_input = Prompt.ask(f"[bold cyan]{USER_NAME}[/bold cyan]")
            if not user_input.strip():
                continue

            clean = user_input.strip()
            lower = clean.lower()

            # ── Built-in CLI commands ──────────────────────────────────────────
            if lower in ("/exit", "exit", "quit", "q"):
                if wake_engine.is_running:
                    wake_engine.stop()
                console.print(f"[bold red]Shutting down {ASSISTANT_NAME} session. Goodbye, {USER_NAME}.[/bold red]")
                speak(f"Shutting down session. Goodbye, {USER_NAME}.")
                break

            if lower in ("/status", "status"):
                print_status_table()
                continue

            # /wake  → toggle on
            # /wake on  → enable
            # /wake off → disable
            # /wake set <phrase> → change wake word
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
                    # Toggle: if running → off, else → on
                    _toggle_wake_word(not wake_engine.is_running)
                continue

            if lower in ("/mic", "mic", "/voice", "voice"):
                console.print("[bold green]🎙️ Listening to microphone... (Speak now)[/bold green]")
                heard = listen(timeout=6.0)
                if not heard:
                    console.print("[dim yellow]No speech detected.[/dim yellow]")
                    continue
                console.print(f"[bold cyan]{USER_NAME} (Voice):[/bold cyan] {heard}")
                clean = heard

            # ── Normal text / voice interaction ───────────────────────────────
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