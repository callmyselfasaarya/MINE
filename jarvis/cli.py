import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt

from jarvis.config import ASSISTANT_NAME, USER_NAME
from jarvis.core.agent import jarvis_agent
from jarvis.voice.stt import listen
from jarvis.voice.tts import speak

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

    ai_mode = f"Gemini ({state['model_name']})" if state["gemini_active"] else "Local Intent Engine (Active)"
    table.add_row("🧠 AI Brain", ai_mode)

    sys_info = state.get("system_status", {})
    cpu = sys_info.get("cpu_usage_percent", "N/A")
    ram = sys_info.get("ram_usage_percent", "N/A")
    table.add_row("🖥️ Hardware", f"CPU: {cpu}% | RAM: {ram}%")

    table.add_row("⏰ Reminders", f"{len(state.get('reminders', []))} pending")
    table.add_row("📅 Calendar", f"{len(state.get('calendar_events', []))} events")
    table.add_row("🧠 Long-Term Memory", f"{len(state.get('memories', []))} facts remembered")
    table.add_row("📁 Documents", f"{len(state.get('documents', []))} files")

    console.print(table)


def run_cli():
    console.print(BANNER)
    print_status_table()

    console.print("\n[dim]Commands: [bold]/mic[/bold] to listen via microphone, [bold]/status[/bold] for vitals, [bold]/exit[/bold] to quit.[/dim]\n")
    speak(f"Greetings, {USER_NAME}. {ASSISTANT_NAME} Version 1 MVP is online and standing by.")

    while True:
        try:
            # Check if pending confirmation
            pending = jarvis_agent.guardrails.get_pending_action()
            if pending:
                console.print(Panel(
                    f"[bold yellow]⚠️ AUTHORIZATION REQUIRED[/bold yellow]\n{pending.prompt_message}\n\n[dim]Type 'yes' / 'confirm' to authorize, or 'no' / 'cancel' to abort.[/dim]",
                    border_style="yellow"
                ))

            user_input = Prompt.ask(f"[bold cyan]{USER_NAME}[/bold cyan]")
            if not user_input.strip():
                continue

            clean = user_input.strip()

            if clean.lower() in ("/exit", "exit", "quit", "q"):
                console.print(f"[bold red]Shutting down {ASSISTANT_NAME} session. Goodbye, {USER_NAME}.[/bold red]")
                speak(f"Shutting down session. Goodbye, {USER_NAME}.")
                break

            if clean.lower() in ("/status", "status"):
                print_status_table()
                continue

            if clean.lower() in ("/mic", "mic", "/voice", "voice"):
                console.print("[bold green]🎙️ Listening to microphone... (Speak now)[/bold green]")
                heard = listen(timeout=6.0)
                if not heard:
                    console.print("[dim yellow]No speech detected.[/dim yellow]")
                    continue
                console.print(f"[bold cyan]{USER_NAME} (Voice):[/bold cyan] {heard}")
                clean = heard

            # Execution trace display
            console.print("[dim cyan]Processing: Speech/Text -> LLM -> Tool Call -> Confirmation -> Response[/dim cyan]")

            result = jarvis_agent.interact(clean, speak_output=True)

            if result.get("tool_called"):
                console.print(f"[bold yellow]⚙️ Executed Tool:[/bold yellow] [bold]{result.get('tool_called')}[/bold]")
                console.print(f"[dim]Args: {result.get('tool_args')}[/dim]")

            # Print assistant response
            response_text = result.get("text", "")
            console.print(Panel(
                Text(response_text, style="bold white"),
                title=f"[bold cyan]{ASSISTANT_NAME}[/bold cyan]",
                border_style="cyan"
            ))

        except (KeyboardInterrupt, EOFError):
            console.print(f"\n[bold red]Terminating {ASSISTANT_NAME} CLI...[/bold red]")
            break
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")


if __name__ == "__main__":
    run_cli()