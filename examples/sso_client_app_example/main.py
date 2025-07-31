import secrets
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import requests
from pathlib import Path

# Import configuration from our local config file
from config import LOLLMS_SERVER_URL, CLIENT_ID, REDIRECT_URI

app = FastAPI(title="SSO Client Example")

# Use a secure, randomly generated key for session cookies.
# In a real production app, you would load this from a secure environment variable.
SESSION_SECRET_KEY = secrets.token_hex(32)

# Add middleware to handle session cookies
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    session_cookie="sso_client_session",
    max_age=3600  # Session expires after 1 hour of inactivity
)

# Setup for rendering HTML templates
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    Renders the home page.
    Shows user info if logged in, otherwise shows a login link.
    """
    user = request.session.get("user")
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/login")
async def login():
    """
    Redirects the user to the LoLLMs SSO server for authentication.
    The LoLLMs server will know which app is requesting login via the client_id in the URL.
    """
    sso_url = f"{LOLLMS_SERVER_URL}/app/{CLIENT_ID}"
    print(f"Redirecting user to LoLLMs SSO: {sso_url}")
    return RedirectResponse(url=sso_url)

@app.get("/sso/callback")
async def sso_callback(request: Request, token: str = None):
    """
    This is the Redirect URI that LoLLMs sends the user back to after a successful login.
    It receives a temporary token which it must verify.
    """
    if not token:
        return HTMLResponse("SSO Error: No token provided.", status_code=400)
    
    print(f"Received SSO callback with token: {token[:30]}...")

    # Step 1: Verify (introspect) the received token with the LoLLMs server
    introspect_url = f"{LOLLMS_SERVER_URL}/api/sso/introspect"
    try:
        response = requests.post(introspect_url, data={"token": token})
        response.raise_for_status()
        introspection_data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error during token introspection: {e}")
        return HTMLResponse("Failed to verify SSO token with LoLLMs server.", status_code=500)

    # Step 2: Check if the token is active and valid
    if not introspection_data.get("active"):
        error_message = introspection_data.get("error", "Token is invalid or expired.")
        print(f"Token introspection failed: {error_message}")
        return HTMLResponse(f"SSO Login Failed: {error_message}", status_code=401)
    
    print("Token introspection successful. User data:", introspection_data.get("user_info"))

    # Step 3: Token is valid. Create a local session for the user.
    # Store the user information received from the SSO server in the session cookie.
    request.session["user"] = introspection_data.get("user_info")
    
    # Step 4: Redirect to a protected page (e.g., the user's profile)
    return RedirectResponse(url="/profile", status_code=303)


@app.get("/profile", response_class=HTMLResponse)
async def profile(request: Request):
    """
    A protected route. It requires a valid user session.
    If the user is not logged in, it redirects them to the login flow.
    """
    user = request.session.get("user")
    if not user:
        # User is not logged in, start the SSO flow
        return RedirectResponse(url="/login")
    
    # User is logged in, render their profile page
    return templates.TemplateResponse("profile.html", {"request": request, "user": user})

@app.get("/logout")
async def logout(request: Request):
    """
    Logs the user out by clearing their local session in this app.
    This does NOT log them out of the main LoLLMs platform.
    """
    request.session.clear()
    return RedirectResponse(url="/")

if __name__ == "__main__":
    import uvicorn
    print("\n--- LoLLMs SSO Client Example App ---")
    print(f"This app is configured for LoLLMs server at: {LOLLMS_SERVER_URL}")
    print(f"It identifies itself with Client ID: {CLIENT_ID}")
    print("Make sure these values in 'config.py' match your LoLLMs App settings.")
    print("Starting server on http://127.0.0.1:8001")
    print("-----------------------------------")
    uvicorn.run(app, host="127.0.0.1", port=8001)