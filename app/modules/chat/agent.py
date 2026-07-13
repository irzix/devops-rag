import re
import uuid
import asyncio
import contextvars
import asyncssh
from typing import List, Tuple
from fastapi import HTTPException, status
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain_core.callbacks import AsyncCallbackHandler
from sqlmodel import select

from app.core.config import settings
from app.core.database import async_session_maker
from app.core.security import decrypt_data
from app.modules.servers.models import Server
from app.modules.servers.service import servers_service
from app.modules.chat.models import AgentAction

# Context variables to track active execution details across async threads
active_websocket = contextvars.ContextVar("active_websocket")
active_session_id = contextvars.ContextVar("active_session_id")
active_owner_id = contextvars.ContextVar("active_owner_id")

class StreamingCallbackHandler(AsyncCallbackHandler):
    """Callback handler to stream LLM generation tokens directly to the active WebSocket."""
    def __init__(self, websocket):
        self.websocket = websocket

    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        try:
            await self.websocket.send_json({
                "type": "token",
                "data": token
            })
        except Exception:
            pass

def get_llm(callbacks=None) -> ChatOpenAI:
    """Initialize OpenRouter LLM client with streaming support."""
    if not settings.OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is not configured in environment")
        
    return ChatOpenAI(
        openai_api_key=settings.OPENROUTER_API_KEY,
        openai_api_base="https://openrouter.ai/api/v1",
        model=settings.OPENROUTER_MODEL,
        temperature=0.0,  # Zero temperature for deterministic system operations
        streaming=True,
        callbacks=callbacks or [],
        default_headers={
            "HTTP-Referer": "https://github.com/irzix/devops-copilot",
            "X-Title": "DevOps Copilot Agent"
        }
    )

def is_write_command(command: str) -> bool:
    """
    Heuristic check to determine if a bash command is state-modifying.
    Read-only commands are allowed to run instantly; others require human verification.
    """
    cmd = command.strip().lower()
    
    # List of safe read-only commands
    read_only_prefixes = (
        "df", "free", "uptime", "uname", "whoami", "hostname", 
        "ps", "top", "htop", "cat", "ls", "grep", "tail", "head", 
        "stat", "systemctl status", "service status"
    )
    
    # Split by common shell execution delimiters to check pipelines
    sub_commands = re.split(r';|&&|\|\||\|', cmd)
    
    for sub in sub_commands:
        sub = sub.strip()
        if not sub:
            continue
        
        is_read = False
        for prefix in read_only_prefixes:
            if sub.startswith(prefix):
                # If command writes outputs via redirection, treat it as a write command
                if ">" not in sub:
                    is_read = True
                    break
        
        if not is_read:
            return True
            
    return False

@tool
async def list_available_servers() -> str:
    """
    Retrieve a list of all target servers currently registered in the database.
    Returns their IDs, names, and IP addresses. Use this tool to discover the server_id before running commands.
    """
    try:
        owner_id = active_owner_id.get()
        async with async_session_maker() as session:
            statement = select(Server).where(Server.owner_id == owner_id)
            result = await session.exec(statement)
            servers = result.all()
            
            if not servers:
                return "No target servers registered yet. Tell the user to register a server first."
            
            output = "Available target servers:\n"
            for s in servers:
                output += f"- ID: {s.id} | Name: {s.name} | Host: {s.ip_address}:{s.ssh_port} | User: {s.ssh_username} | Auth: {s.ssh_auth_type}\n"
            return output
    except Exception as e:
        return f"Error retrieving server list: {str(e)}"

@tool
async def execute_ssh_command(server_id: int | str, command: str) -> str:
    """
    Execute a terminal command asynchronously on a target server via SSH.
    First runs semantic security checks and determines if human-in-the-loop approval is required.
    Streams execution logs line-by-line in real-time to the active terminal session.
    """
    try:
        # 1. Run semantic safety guardrail
        from app.modules.guardrails.service import is_command_safe
        is_safe, warning, similarity = is_command_safe(command)
        if not is_safe:
            return f"Execution Blocked by Guardrail: {warning} (similarity index: {similarity:.2f})"

        # 2. Enforce human verification for state-modifying actions
        if is_write_command(command):
            action_id = f"act_{uuid.uuid4().hex[:12]}"
            sess_id = active_session_id.get()
            owner_id = active_owner_id.get()
            
            async with async_session_maker() as session:
                # Check server ownership
                try:
                    # Check if server_id is an integer or digit string
                    is_id = False
                    if isinstance(server_id, int):
                        is_id = True
                    elif isinstance(server_id, str) and server_id.isdigit():
                        is_id = True
                        server_id = int(server_id)
                        
                    if is_id:
                        server = await servers_service.get_server_by_id(session, server_id, owner_id)
                    else:
                        server = await servers_service.get_server_by_name(session, str(server_id), owner_id)
                except Exception:
                    return f"Error: Server '{server_id}' not found or permission denied."
                
                # Record the pending action in database
                action = AgentAction(
                    id=action_id,
                    session_id=sess_id,
                    server_id=server.id,
                    command=command,
                    status="pending"
                )
                session.add(action)
                await session.commit()
                
            # Emit approval notification to WebSocket client
            ws = active_websocket.get()
            await ws.send_json({
                "type": "approval_required",
                "action_id": action_id,
                "server_name": server.name,
                "command": command
            })
            
            # Return special status string to halt agent execution loop
            return f"PAUSED: REQUIRES_APPROVAL: {action_id}"

        # 3. Safe read-only execution: connect and stream output line-by-line
        owner_id = active_owner_id.get()
        async with async_session_maker() as session:
            try:
                # Check if server_id is an integer or digit string
                is_id = False
                if isinstance(server_id, int):
                    is_id = True
                elif isinstance(server_id, str) and server_id.isdigit():
                    is_id = True
                    server_id = int(server_id)
                    
                if is_id:
                    server = await servers_service.get_server_by_id(session, server_id, owner_id)
                else:
                    server = await servers_service.get_server_by_name(session, str(server_id), owner_id)
            except Exception:
                return f"Error: Server '{server_id}' not found."

        credential = decrypt_data(server.encrypted_credential)
        conn_args = {
            "host": server.ip_address,
            "port": server.ssh_port,
            "username": server.ssh_username,
            "known_hosts": None,
        }
        
        if server.ssh_auth_type == "password":
            conn_args["password"] = credential
        else:
            try:
                conn_args["client_keys"] = [asyncssh.import_private_key(credential)]
            except Exception as e:
                return f"Error: Invalid SSH private key format: {str(e)}"

        ws = active_websocket.get()
        await ws.send_json({
            "type": "stdout",
            "data": f"\n[Executing on {server.name}]: {command}\n"
        })

        stdout_accumulated = []
        stderr_accumulated = []

        async def run_with_timeout():
            async with asyncssh.connect(**conn_args) as conn:
                async with conn.create_process(command) as process:
                    # Stream stdout line-by-line
                    async for line in process.stdout:
                        if isinstance(line, bytes):
                            line = line.decode("utf-8", errors="replace")
                        stdout_accumulated.append(line)
                        await ws.send_json({"type": "stdout", "data": line})
                    
                    # Stream stderr line-by-line
                    async for line in process.stderr:
                        if isinstance(line, bytes):
                            line = line.decode("utf-8", errors="replace")
                        stderr_accumulated.append(line)
                        await ws.send_json({"type": "stderr", "data": line})
                    
                    exit_status = await process.wait()
                    exit_code = exit_status.exit_status if exit_status.exit_status is not None else 0
                    
                    await ws.send_json({
                        "type": "stdout",
                        "data": f"[Process finished with code {exit_code}]\n"
                    })
                    
                    stdout_str = "".join(stdout_accumulated)
                    stderr_str = "".join(stderr_accumulated)

                    # Auto-index execution output into RAG knowledge base
                    try:
                        from app.modules.knowledge.service import index_command_output
                        index_command_output(server.name, command, stdout_str, stderr_str, exit_code)
                    except Exception:
                        pass  # Non-critical: don't break execution if indexing fails

                    return f"Exit Code: {exit_code}\nStdout:\n{stdout_str}\nStderr:\n{stderr_str}"

        try:
            return await asyncio.wait_for(run_with_timeout(), timeout=30.0)
        except asyncio.TimeoutError:
            return f"Error: Command execution timed out after 30 seconds on {server.name}."
    except Exception as e:
        return f"Tool Execution Error: {str(e)}"


@tool
async def search_knowledge(query: str, sources: list[str] | None = None) -> str:
    """
    Search the DevOps knowledge base for previously collected information.
    Sources can include: 'command_history', 'server_logs', 'server_configs'.
    If sources is None, all collections are searched.
    Use this tool to recall past command outputs, server logs, or config file contents.
    """
    try:
        from app.modules.knowledge.service import search
        return search(query, collection_names=sources, n_results=3)
    except Exception as e:
        return f"Knowledge search error: {str(e)}"


@tool
async def fetch_server_logs(server_id: int | str, log_source: str = "journalctl -n 100 --no-pager") -> str:
    """
    Fetch recent logs from a target server via SSH, stream them to the user, and auto-index them.
    Default log source is journalctl. Can also use: 'tail -n 100 /var/log/syslog', etc.
    """
    try:
        owner_id = active_owner_id.get()
        async with async_session_maker() as session:
            try:
                is_id = isinstance(server_id, int) or (isinstance(server_id, str) and server_id.isdigit())
                if is_id:
                    server = await servers_service.get_server_by_id(session, int(server_id) if isinstance(server_id, str) else server_id, owner_id)
                else:
                    server = await servers_service.get_server_by_name(session, str(server_id), owner_id)
            except Exception:
                return f"Error: Server '{server_id}' not found."

        credential = decrypt_data(server.encrypted_credential)
        conn_args = {
            "host": server.ip_address,
            "port": server.ssh_port,
            "username": server.ssh_username,
            "known_hosts": None,
        }
        if server.ssh_auth_type == "password":
            conn_args["password"] = credential
        else:
            conn_args["client_keys"] = [asyncssh.import_private_key(credential)]

        ws = active_websocket.get()
        await ws.send_json({"type": "stdout", "data": f"\n[Fetching logs from {server.name}]: {log_source}\n"})

        async def run_logs_with_timeout():
            async with asyncssh.connect(**conn_args) as conn:
                result = await conn.run(log_source, check=False)
                stdout = result.stdout or ""
                if isinstance(stdout, bytes):
                    stdout = stdout.decode("utf-8", errors="replace")
                await ws.send_json({"type": "stdout", "data": stdout})
                return stdout

        try:
            stdout = await asyncio.wait_for(run_logs_with_timeout(), timeout=30.0)
        except asyncio.TimeoutError:
            return f"Error: Fetching logs timed out after 30 seconds on {server.name}."

        # Auto-index fetched logs
        try:
            from app.modules.knowledge.service import index_log
            index_log(server.name, log_source, stdout)
        except Exception:
            pass

        return f"Fetched {len(stdout)} chars of logs from {server.name}.\n{stdout[:2000]}"
    except Exception as e:
        return f"Error fetching logs: {str(e)}"


@tool
async def fetch_server_config(server_id: int | str, file_path: str) -> str:
    """
    Read a config file from a target server via SSH (e.g. /etc/nginx/nginx.conf),
    stream it to the user, and auto-index it for future reference.
    """
    try:
        owner_id = active_owner_id.get()
        async with async_session_maker() as session:
            try:
                is_id = isinstance(server_id, int) or (isinstance(server_id, str) and server_id.isdigit())
                if is_id:
                    server = await servers_service.get_server_by_id(session, int(server_id) if isinstance(server_id, str) else server_id, owner_id)
                else:
                    server = await servers_service.get_server_by_name(session, str(server_id), owner_id)
            except Exception:
                return f"Error: Server '{server_id}' not found."

        credential = decrypt_data(server.encrypted_credential)
        conn_args = {
            "host": server.ip_address,
            "port": server.ssh_port,
            "username": server.ssh_username,
            "known_hosts": None,
        }
        if server.ssh_auth_type == "password":
            conn_args["password"] = credential
        else:
            conn_args["client_keys"] = [asyncssh.import_private_key(credential)]

        ws = active_websocket.get()
        await ws.send_json({"type": "stdout", "data": f"\n[Reading {file_path} from {server.name}]\n"})

        async def run_config_with_timeout():
            async with asyncssh.connect(**conn_args) as conn:
                result = await conn.run(f"cat {file_path}", check=False)
                stdout = result.stdout or ""
                if isinstance(stdout, bytes):
                    stdout = stdout.decode("utf-8", errors="replace")
                stderr = result.stderr or ""
                if isinstance(stderr, bytes):
                    stderr = stderr.decode("utf-8", errors="replace")

                if result.exit_status != 0:
                    return f"Error reading {file_path}: {stderr}"

                await ws.send_json({"type": "stdout", "data": stdout})
                return stdout

        try:
            res = await asyncio.wait_for(run_config_with_timeout(), timeout=30.0)
            if res.startswith("Error reading"):
                return res
            stdout = res
        except asyncio.TimeoutError:
            return f"Error: Reading config timed out after 30 seconds on {server.name}."

        # Auto-index the config file
        try:
            from app.modules.knowledge.service import index_config
            index_config(server.name, file_path, stdout)
        except Exception:
            pass

        return f"Config file {file_path} from {server.name}:\n{stdout[:3000]}"
    except Exception as e:
        return f"Error fetching config: {str(e)}"


@tool
async def record_lesson_learned(
    server_id: int | str,
    problem: str,
    real_cause: str,
    what_didnt_work: str,
    what_worked: str,
    time_to_resolve: str
) -> str:
    """
    Record a structured lesson learned (postmortem) after successfully resolving an incident or bug on a server.
    This populates the knowledge base (ExpeL/Reflexion) to resolve similar issues instantly next time.
    """
    try:
        owner_id = active_owner_id.get()
        async with async_session_maker() as session:
            try:
                is_id = isinstance(server_id, int) or (isinstance(server_id, str) and server_id.isdigit())
                if is_id:
                    server = await servers_service.get_server_by_id(session, int(server_id) if isinstance(server_id, str) else server_id, owner_id)
                else:
                    server = await servers_service.get_server_by_name(session, str(server_id), owner_id)
            except Exception:
                return f"Error: Server '{server_id}' not found."

        from app.modules.knowledge.service import index_lesson_learned
        index_lesson_learned(
            server_name=server.name,
            problem=problem,
            real_cause=real_cause,
            what_didnt_work=what_didnt_work,
            what_worked=what_worked,
            time_to_resolve=time_to_resolve
        )
        return f"Lesson Learned recorded for {server.name}: Problem '{problem}' resolved via '{what_worked}'."
    except Exception as e:
        return f"Error recording lesson learned: {str(e)}"


@tool
async def search_lessons_learned(query: str) -> str:
    """
    Semantic search across structured past lessons learned (postmortems).
    Always call this before troubleshooting an incident or error to see what worked and what didn't work previously.
    """
    try:
        from app.modules.knowledge.service import search_lessons_learned as _search_lessons
        return _search_lessons(query)
    except Exception as e:
        return f"Error searching lessons learned: {str(e)}"


# Define list of tools available to the Agent
tools = [
    list_available_servers,
    execute_ssh_command,
    search_knowledge,
    fetch_server_logs,
    fetch_server_config,
    record_lesson_learned,
    search_lessons_learned,
]

# Setup agent prompt template
system_prompt = """You are a highly capable DevOps AI Assistant managing servers via SSH.
You have tools to list servers, execute commands, fetch logs/configs, search past knowledge, and record/search structured lessons learned.

IMPORTANT INSTRUCTIONS:
1. Always call `list_available_servers` first if you do not know the server_id.
2. EXPERIENTIAL LEARNING PROTOCOL (ExpeL / Reflexion):
   - Before debugging or troubleshooting ANY server error or incident: ALWAYS call `search_lessons_learned` first to check if a similar issue occurred before. Pay close attention to "What didn't work" to avoid dead ends.
   - After successfully resolving a server issue, bug, or incident: ALWAYS call `record_lesson_learned` with the structured breakdown (Problem, Real Cause, What didn't work, What worked, Time to Resolve).
3. Use `search_knowledge` to recall general past command outputs, logs, or configs before re-running commands.
4. Use `fetch_server_logs` to pull and index server logs (journalctl, syslog, etc.).
5. Use `fetch_server_config` to read and index config files (nginx, systemd, etc.).
6. Any command you execute will be checked by a semantic guardrail.
7. If a tool returns 'PAUSED: REQUIRES_APPROVAL: <action_id>', you MUST:
   - STOP all execution immediately. Do not attempt to call any other tools.
   - Reply to the user explaining that the command requires their approval.
   - Explicitly mention the Action ID: '<action_id>'.
8. Be concise and report the final outputs clearly.
"""

def create_agent_executor(callbacks=None):
    """Initialize agent compiled StateGraph using modern LangChain create_agent."""
    llm = get_llm(callbacks=callbacks)
    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt
    )
