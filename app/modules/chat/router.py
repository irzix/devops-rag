import jwt
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from langchain_core.messages import HumanMessage, AIMessage

from app.core.config import settings
from app.core.database import get_session, async_session_maker
from app.modules.auth import User
from app.modules.auth.service import get_current_user
from app.modules.servers.models import Server
from app.modules.servers.service import servers_service
from app.modules.chat.models import ChatSession, ChatMessage, AgentAction
from app.modules.chat.schema import (
    ChatSessionCreate,
    ChatSessionResponse,
    ChatMessageResponse,
    AgentActionResponse
)
from app.modules.chat.agent import (
    create_agent_executor,
    StreamingCallbackHandler,
    active_websocket,
    active_session_id,
    active_owner_id,
    decrypt_data,
    asyncssh
)

router = APIRouter()

# --- REST Endpoints for Chat History ---

@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Create a new chat session thread for the logged-in administrator."""
    new_session = ChatSession(title=payload.title, user_id=current_user.id)
    session.add(new_session)
    await session.commit()
    await session.refresh(new_session)
    return new_session

@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Retrieve all chat sessions belonging to the current administrator."""
    statement = select(ChatSession).where(ChatSession.user_id == current_user.id).order_by(ChatSession.created_at.desc())
    result = await session.exec(statement)
    return result.all()

@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
async def get_messages(
    session_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Retrieve historical messages for a specific chat session thread."""
    # Verify session ownership
    sess_statement = select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
    sess_result = await session.exec(sess_statement)
    if not sess_result.first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")

    msg_statement = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc())
    msg_result = await session.exec(msg_statement)
    return msg_result.all()

# --- WebSocket Real-Time Chat & Execution Tunnel ---

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...)
):
    """
    Establish a WebSocket connection for real-time DevOps chat and live execution logging.
    Validates the admin's JWT token query parameter prior to connection acceptance.
    """
    # 1. Manual JWT Token Verification for Handshake
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        username = payload.get("sub")
        if not username:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        async with async_session_maker() as session:
            statement = select(User).where(User.username == username)
            result = await session.exec(statement)
            user = result.first()
            if not user or not user.is_active:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Accept client WebSocket connection
    await websocket.accept()

    try:
        while True:
            # Receive inbound JSON payloads
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "message":
                session_id = data.get("session_id")
                content = data.get("content")

                if not session_id or not content:
                    continue

                # 2. Load conversation history for memory injection
                async with async_session_maker() as db_session:
                    # Verify session ownership
                    sess_stmt = select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user.id)
                    sess = await db_session.exec(sess_stmt)
                    if not sess.first():
                        await websocket.send_json({"type": "error", "data": "Unauthorized session access"})
                        continue

                    # Record user message in DB
                    user_msg = ChatMessage(session_id=session_id, sender="user", content=content)
                    db_session.add(user_msg)
                    await db_session.commit()

                    # Fetch history
                    history_stmt = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc())
                    history_result = await db_session.exec(history_stmt)
                    db_messages = history_result.all()

                chat_history = []
                # Map history database records to LangChain Human/AI message formats
                for msg in db_messages[:-1]:  # Exclude current message since it is input
                    if msg.sender == "user":
                        chat_history.append(HumanMessage(content=msg.content))
                    else:
                        chat_history.append(AIMessage(content=msg.content))

                # 3. Setup context variables for the SSH execution tools
                ws_token = active_websocket.set(websocket)
                sess_token = active_session_id.set(session_id)
                owner_token = active_owner_id.set(user.id)

                try:
                    # Stream tokens via custom callback handler
                    callback = StreamingCallbackHandler(websocket)
                    agent_executor = create_agent_executor(callbacks=[callback])

                    # Invoke agent compiled StateGraph using messages schema
                    inputs = {
                        "messages": chat_history + [HumanMessage(content=content)]
                    }
                    agent_response = await agent_executor.ainvoke(inputs)

                    # Extract final text from output message list
                    ai_text = agent_response["messages"][-1].content
                    
                    # Record final agent response in database
                    async with async_session_maker() as db_session:
                        ai_msg = ChatMessage(session_id=session_id, sender="ai", content=ai_text)
                        db_session.add(ai_msg)
                        await db_session.commit()

                    # Notify client execution complete
                    await websocket.send_json({
                        "type": "finished",
                        "data": ai_text
                    })

                except Exception as e:
                    await websocket.send_json({"type": "error", "data": f"Agent Execution Error: {str(e)}"})
                finally:
                    # Clean context variables
                    active_websocket.reset(ws_token)
                    active_session_id.reset(sess_token)
                    active_owner_id.reset(owner_token)

            elif msg_type == "approve" or msg_type == "reject":
                action_id = data.get("action_id")
                if not action_id:
                    continue

                async with async_session_maker() as db_session:
                    # Fetch queued action
                    act_stmt = select(AgentAction).where(AgentAction.id == action_id)
                    act_result = await db_session.exec(act_stmt)
                    action = act_result.first()

                    if not action or action.status != "pending":
                        await websocket.send_json({"type": "error", "data": "Action not found or already processed"})
                        continue

                    # Verify session ownership
                    sess_stmt = select(ChatSession).where(ChatSession.id == action.session_id, ChatSession.user_id == user.id)
                    sess = await db_session.exec(sess_stmt)
                    if not sess.first():
                        await websocket.send_json({"type": "error", "data": "Unauthorized session access"})
                        continue

                    if msg_type == "reject":
                        action.status = "rejected"
                        await db_session.commit()
                        await websocket.send_json({
                            "type": "stdout",
                            "data": f"\n[Action {action_id} Rejected by User]\n"
                        })
                        continue

                    # If approved, update status
                    action.status = "approved"
                    await db_session.commit()

                    # Load targeted server config
                    server_stmt = select(Server).where(Server.id == action.server_id)
                    srv_result = await db_session.exec(server_stmt)
                    server = srv_result.first()

                await websocket.send_json({
                    "type": "stdout",
                    "data": f"\n[Action {action_id} Approved] Running command on {server.name}...\n"
                })

                # 4. Decrypt and execute approved write command
                credential = decrypt_data(server.encrypted_credential)
                conn_args = {
                    "host": server.ip_address,
                    "port": server.ssh_port,
                    "username": server.ssh_username,
                    "known_hosts": None
                }
                if server.ssh_auth_type == "password":
                    conn_args["password"] = credential
                else:
                    conn_args["client_keys"] = [asyncssh.import_private_key(credential)]

                stdout_accumulated = []
                stderr_accumulated = []
                exit_status = -1

                try:
                    # Connect and execute process, streaming stdout/stderr line-by-line
                    async with asyncssh.connect(**conn_args) as conn:
                        async with conn.create_process(action.command) as process:
                            async for line in process.stdout:
                                if isinstance(line, bytes):
                                    line = line.decode("utf-8", errors="replace")
                                stdout_accumulated.append(line)
                                await websocket.send_json({"type": "stdout", "data": line})
                            async for line in process.stderr:
                                if isinstance(line, bytes):
                                    line = line.decode("utf-8", errors="replace")
                                stderr_accumulated.append(line)
                                await websocket.send_json({"type": "stderr", "data": line})
                            exit_status = await process.wait()
                            exit_code = exit_status.exit_status if exit_status.exit_status is not None else 0

                    await websocket.send_json({
                        "type": "stdout",
                        "data": f"[Process finished with code {exit_code}]\n"
                    })

                    stdout_str = "".join(stdout_accumulated)
                    stderr_str = "".join(stderr_accumulated)

                    # Auto-index approved command output into RAG knowledge base
                    try:
                        from app.modules.knowledge.service import index_command_output
                        index_command_output(server.name, action.command, stdout_str, stderr_str, exit_code)
                    except Exception:
                        pass

                    # 5. Invoke agent loop with the execution output
                    ws_token = active_websocket.set(websocket)
                    sess_token = active_session_id.set(action.session_id)
                    owner_token = active_owner_id.set(user.id)

                    try:
                        callback = StreamingCallbackHandler(websocket)
                        agent_executor = create_agent_executor(callbacks=[callback])

                        # Feed output back to agent reasoning chain
                        resume_prompt = (
                            f"User approved execution of action '{action_id}'.\n"
                            f"Command '{action.command}' executed on server '{server.name}'.\n"
                            f"Exit Code: {exit_code}\n"
                            f"Stdout:\n{stdout_str}\n"
                            f"Stderr:\n{stderr_str}\n\n"
                            f"Please analyze these outputs and provide your final response to the user."
                        )

                        # Invoke the agent graph with the resume message
                        agent_response = await agent_executor.ainvoke({
                            "messages": [HumanMessage(content=resume_prompt)]
                        })

                        ai_text = agent_response["messages"][-1].content
                        
                        # Save final summary response in database
                        async with async_session_maker() as db_session:
                            ai_msg = ChatMessage(session_id=action.session_id, sender="ai", content=ai_text)
                            db_session.add(ai_msg)
                            await db_session.commit()

                        await websocket.send_json({
                            "type": "finished",
                            "data": ai_text
                        })

                    except Exception as e:
                        await websocket.send_json({"type": "error", "data": f"Error during agent completion: {str(e)}"})
                    finally:
                        active_websocket.reset(ws_token)
                        active_session_id.reset(sess_token)
                        active_owner_id.reset(owner_token)

                except Exception as e:
                    await websocket.send_json({"type": "error", "data": f"SSH Execution Failed: {str(e)}"})

    except WebSocketDisconnect:
        pass
