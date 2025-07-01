from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status, HTTPException, Depends
from sqlalchemy.orm import Session

# Import the specific functions and objects needed from your session file
from backend.session import get_current_db_user_from_token
from backend.database_setup import get_db
from backend.ws_manager import manager

dm_ws_router = APIRouter(
    prefix="/ws/dm",
    tags=["Direct Messages - WebSocket"],
)

@dm_ws_router.websocket("/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """
    Handles the WebSocket connection for a user.
    The user is authenticated via the JWT token provided in the URL.
    This is adapted to use the project's existing session logic.
    """
    # We need a database session to authenticate the user
    db_gen = get_db()
    db: Session = next(db_gen)
    
    try:
        # Step 1: Authenticate the user from the token using the existing function.
        # We manually call the logic that `Depends` would normally handle.
        user = await get_current_db_user_from_token(token=token, db=db)
        if not user or not user.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        user_id = user.id
    except HTTPException:
        # If the token is invalid or the user is not found, reject the connection.
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    finally:
        # Ensure the database session is closed
        db.close()

    # Step 2: Add the authenticated user to the connection manager.
    await manager.connect(user_id, websocket)

    try:
        # Step 3: Keep the connection alive.
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception as e:
        print(f"Error in WebSocket for user {user_id}: {e}")
        manager.disconnect(user_id)
        # It's good practice to try and close the websocket gracefully
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except RuntimeError:
            # This can happen if the socket is already dead
            pass