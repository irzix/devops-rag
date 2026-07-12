import re
import uuid
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
            "HTTP-Referer": "https://github.com/irzix/devops-rag",
            "X-Title": "DevOps RAG Agent"
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
async def execute_ssh_command(server_id: int, command: str) -> str:
    """
    Execute a terminal command asynchronously on a target server via SSH.
    First runs semantic security checks and determines if human-in-the-loop approval is required.
    Streams execution logs line-by-line in real-time to the active terminal session.
    """
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
                server = await servers_service.get_server_by_id(session, server_id, owner_id)
            except Exception:
                return f"Error: Server with ID {server_id} not found or permission denied."
            
            # Record the pending action in database
            action = AgentAction(
                id=action_id,
                session_id=sess_id,
                server_id=server_id,
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
            server = await servers_service.get_server_by_id(session, server_id, owner_id)
        except Exception:
            return f"Error: Server with ID {server_id} not found."

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
    await ws.send_json({
        "type": "stdout",
        "data": f"\n[Executing on {server.name}]: {command}\n"
    })

    stdout_accumulated = []
    stderr_accumulated = []

    try:
        async with asyncssh.connect(**conn_args) as conn:
            async with conn.create_process(command) as process:
                # Stream stdout line-by-line
                async for line in process.stdout:
                    stdout_accumulated.append(line)
                    await ws.send_json({"type": "stdout", "data": line})
                
                # Stream stderr line-by-line
                async for line in process.stderr:
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
                return f"Exit Code: {exit_code}\nStdout:\n{stdout_str}\nStderr:\n{stderr_str}"
    except Exception as e:
        return f"SSH Connection Failed to {server.ip_address}: {str(e)}"

# Define list of tools available to the Agent
tools = [list_available_servers, execute_ssh_command]

# Setup agent prompt template
system_prompt = """You are a highly capable DevOps AI Assistant managing servers via SSH.
You have tools to list available servers and execute bash commands on those servers.

IMPORTANT SECURITY INSTRUCTIONS:
1. Always call `list_available_servers` first if you do not know the server_id.
2. Any command you execute will be checked by a semantic guardrail.
3. If a tool returns 'PAUSED: REQUIRES_APPROVAL: <action_id>', you MUST:
   - STOP all execution immediately. Do not attempt to call any other tools.
   - Reply to the user explaining that the command requires their approval.
   - Explicitly mention the Action ID: '<action_id>'.
4. Be concise and report the final outputs clearly.
"""

def create_agent_executor(callbacks=None):
    """Initialize agent compiled StateGraph using modern LangChain create_agent."""
    llm = get_llm(callbacks=callbacks)
    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt
    )
