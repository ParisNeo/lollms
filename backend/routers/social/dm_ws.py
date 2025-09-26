# backend/routers/social/dm_ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status, HTTPException, Depends
from sqlalchemy.orm import Session
from ascii_colors import ASCIIColors

from backend.session import get_current_db_user_from_token
from backend.db import get_db
from backend.ws_manager import manager

dm_ws_router = APIRouter(
    prefix="/ws/dm",
    tags=["Direct Messages - WebSocket"],
)

@dm_ws_router.websocket("/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    ASCIIColors.info(f"[WebSocket] New connection attempt received for token: ...{token[-6:]}")
    db_gen = get_db()
    db: Session = next(db_gen)
    
    user_id = None
    is_admin = False
    username = "unknown"
    
    try:
        user = await get_current_db_user_from_token(token=token, db=db)
        if not user or not user.is_active:
            ASCIIColors.warning(f"[WebSocket] Authentication failed or user inactive for token: ...{token[-6:]}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        user_id = user.id
        is_admin = user.is_admin
        username = user.username
        ASCIIColors.green(f"[WebSocket] User '{username}' (ID: {user_id}) authenticated for WebSocket.")

    except HTTPException:
        ASCIIColors.error(f"[WebSocket] Authentication raised HTTPException for token: ...{token[-6:]}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    finally:
        db.close()

    await manager.connect(user_id, websocket)
    if is_admin:
        manager.register_admin(user_id)

    try:
        while True:
            # Keep the connection alive
            await websocket.receive_text()

    except WebSocketDisconnect:
        ASCIIColors.yellow(f"[WebSocket] User '{username}' (ID: {user_id}) disconnected.")
    except Exception as e:
        ASCIIColors.error(f"[WebSocket] Error in WebSocket for user '{username}' (ID: {user_id}): {e}")
    finally:
        if is_admin:
            manager.unregister_admin(user_id)
        if user_id is not None:
            manager.disconnect(user_id, websocket)
        try:
            # Ensure the websocket is closed if it's not already
            if websocket.client_state != 3: # WebSocketState.DISCONNECTED
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except RuntimeError:
            pass