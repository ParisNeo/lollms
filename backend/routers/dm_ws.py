from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status, HTTPException, Depends
from sqlalchemy.orm import Session

from backend.session import get_current_db_user_from_token
from backend.db import get_db
from backend.ws_manager import manager

dm_ws_router = APIRouter(
    prefix="/ws/dm",
    tags=["Direct Messages - WebSocket"],
)

@dm_ws_router.websocket("/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    db_gen = get_db()
    db: Session = next(db_gen)
    
    user_id = None
    is_admin = False
    
    try:
        user = await get_current_db_user_from_token(token=token, db=db)
        if not user or not user.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        user_id = user.id
        is_admin = user.is_admin

    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    finally:
        db.close()

    await manager.connect(user_id, websocket)
    if is_admin:
        manager.register_admin(user_id)

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        if is_admin:
            manager.unregister_admin(user_id)
        if user_id is not None:
            manager.disconnect(user_id)
    except Exception as e:
        print(f"Error in WebSocket for user {user_id}: {e}")
        if is_admin:
            manager.unregister_admin(user_id)
        if user_id is not None:
            manager.disconnect(user_id)
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except RuntimeError:
            pass