import asyncio
import sys
import json
import httpx
import websockets
import typer
from typing import Optional

from app.cli.config import load_config, save_config

app = typer.Typer(name="devops-rag", help="AI-driven DevOps Agent CLI Client")

@app.command("login")
def login(
    server_url: Optional[str] = typer.Option(None, help="The base URL of the FastAPI backend server"),
    username: Optional[str] = typer.Option(None, help="Your administrator username")
):
    """
    Authenticate with the central DevOps-RAG backend and retrieve an access token.
    Saves configurations locally in ~/.config/devops-rag/config.json.
    """
    if not server_url:
        server_url = typer.prompt("Enter DevOps Agent server URL (e.g. http://localhost:8000)")
    if not username:
        username = typer.prompt("Enter admin username")
    password = typer.prompt("Enter password", hide_input=True)

    server_url_clean = server_url.rstrip("/")
    token_url = f"{server_url_clean}/api/v1/auth/token"

    typer.echo(f"Logging in to {server_url_clean}...")
    try:
        response = httpx.post(
            token_url,
            data={"username": username, "password": password},
            timeout=10.0
        )
        if response.status_code == 200:
            token_data = response.json()
            token = token_data.get("access_token")
            save_config(server_url_clean, token)
            typer.secho("Success! Authenticated and configured locally.", fg=typer.colors.GREEN, bold=True)
        else:
            detail = response.json().get("detail", "Invalid username or password")
            typer.secho(f"Authentication Failed: {detail}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"Connection Error: {str(e)}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

async def run_chat_loop(server_url: str, token: str, session_id: int):
    """Asynchronous WebSocket loop that handles message passing and streams."""
    ws_proto = "wss" if server_url.startswith("https") else "ws"
    host_port = server_url.split("://")[-1]
    ws_url = f"{ws_proto}://{host_port}/api/v1/chat/ws?token={token}"

    try:
        async with websockets.connect(ws_url) as ws:
            typer.secho(f"\nConnected to DevOps AI Agent (Session #{session_id})!", fg=typer.colors.GREEN, bold=True)
            typer.secho("Type your prompt and press Enter. Type 'exit' to quit.\n", fg=typer.colors.CYAN)

            while True:
                # Read user input from terminal
                user_input = typer.prompt("You")
                if user_input.lower() in ("exit", "quit"):
                    typer.secho("Exiting chat session. Goodbye!", fg=typer.colors.YELLOW)
                    break
                
                if not user_input.strip():
                    continue

                # Send chat message to server using websockets API (send stringified JSON)
                await ws.send(json.dumps({
                    "type": "message",
                    "session_id": session_id,
                    "content": user_input
                }))

                # Listen to streamed server events
                typer.secho("Agent: ", fg=typer.colors.MAGENTA, nl=False)
                
                while True:
                    event = await ws.recv()
                    event_data = json.loads(event)
                    event_type = event_data.get("type")

                    if event_type == "token":
                        # Print thinking tokens as they arrive
                        sys.stdout.write(event_data.get("data", ""))
                        sys.stdout.flush()
                    
                    elif event_type == "stdout":
                        # Stream command output in gray
                        sys.stdout.write("\n")  # Newline to separate from previous tokens
                        typer.secho(event_data.get("data", ""), fg=typer.colors.BRIGHT_BLACK, nl=False)
                        sys.stdout.flush()
                        
                    elif event_type == "stderr":
                        # Stream stderr in red
                        sys.stdout.write("\n")
                        typer.secho(event_data.get("data", ""), fg=typer.colors.RED, nl=False)
                        sys.stdout.flush()

                    elif event_type == "approval_required":
                        # Handle human-in-the-loop validation request
                        action_id = event_data.get("action_id")
                        server_name = event_data.get("server_name")
                        command = event_data.get("command")

                        typer.secho(f"\n\n[Action Approval Required]", fg=typer.colors.YELLOW, bold=True)
                        typer.secho(f"Target Server: {server_name}", fg=typer.colors.YELLOW)
                        typer.secho(f"Command to Run: {command}", fg=typer.colors.YELLOW, bold=True)
                        
                        approve = typer.confirm("Approve execution of this command?")
                        
                        if approve:
                            typer.secho("Approving command execution...", fg=typer.colors.GREEN)
                            await ws.send(json.dumps({
                                "type": "approve",
                                "action_id": action_id
                            }))
                        else:
                            typer.secho("Rejecting command execution.", fg=typer.colors.RED)
                            await ws.send(json.dumps({
                                "type": "reject",
                                "action_id": action_id
                            }))

                    elif event_type == "finished":
                        # Output generation is completed
                        # Print newline and final summary response if not fully printed
                        sys.stdout.write("\n\n")
                        break

                    elif event_type == "error":
                        typer.secho(f"\nError: {event_data.get('data')}", fg=typer.colors.RED, err=True)
                        break

    except websockets.exceptions.ConnectionClosed:
        typer.secho("\nConnection disconnected by server.", fg=typer.colors.YELLOW)
    except Exception as e:
        typer.secho(f"\nWebSocket Connection Failed: {str(e)}", fg=typer.colors.RED, err=True)

@app.command("chat")
def chat():
    """
    Start an interactive chat session with the AI DevOps agent in the terminal.
    Allows selecting historical threads or spawning new sessions.
    """
    config = load_config()
    if not config:
        typer.secho("Error: No configuration found. Please run 'devops-rag login' first.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    server_url = config["server_url"]
    token = config["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Fetch existing chat sessions
    typer.echo("Fetching chat sessions from server...")
    try:
        response = httpx.get(f"{server_url}/api/v1/chat/sessions", headers=headers, timeout=10.0)
        if response.status_code == 401:
            typer.secho("Session expired. Please run 'devops-rag login' again.", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        response.raise_for_status()
        sessions = response.json()
    except Exception as e:
        typer.secho(f"Failed to fetch sessions: {str(e)}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # 2. Let the user choose or spawn a new session
    session_id = None
    if sessions:
        typer.echo("\nAvailable chat sessions:")
        for idx, s in enumerate(sessions):
            typer.echo(f"  [{idx + 1}] Session ID: {s['id']} | Title: {s['title']}")
        
        choice = typer.prompt("\nSelect session number, or type 'new' to start a new chat")
        
        if choice.lower() != "new":
            try:
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(sessions):
                    session_id = sessions[choice_idx]["id"]
                else:
                    typer.secho("Invalid choice index.", fg=typer.colors.RED)
                    raise typer.Exit(code=1)
            except ValueError:
                typer.secho("Invalid input format.", fg=typer.colors.RED)
                raise typer.Exit(code=1)

    if session_id is None:
        # Create a new session
        title = typer.prompt("Enter title for the new chat session")
        try:
            res = httpx.post(
                f"{server_url}/api/v1/chat/sessions",
                headers=headers,
                json={"title": title},
                timeout=10.0
            )
            res.raise_for_status()
            new_sess = res.json()
            session_id = new_sess["id"]
        except Exception as e:
            typer.secho(f"Failed to create new session: {str(e)}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)

    # 3. Enter the async WebSocket execution loop
    asyncio.run(run_chat_loop(server_url, token, session_id))

if __name__ == "__main__":
    app()
