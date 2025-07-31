# sso_client_app_example/config.py

# --- Configuration for this Sample SSO Client App ---
# You must fill these values out after creating the corresponding App in the LoLLMs UI.

# The base URL of your LoLLMs instance.
# Example: "http://localhost:9642"
LOLLMS_SERVER_URL = "http://localhost:9642"

# The Client ID you set for this app in the LoLLMs UI.
# This is used to identify which application is requesting authentication.
# Example: "fastapi_sso_example"
CLIENT_ID = "fastapi_sso_example"

# The SSO Secret generated for this app in the LoLLMs UI.
# This is used by the app to securely communicate with the LoLLMs server.
# IMPORTANT: Keep this secret confidential.
CLIENT_SECRET = "PASTE_YOUR_GENERATED_SSO_SECRET_HERE"

# The full URL where this application will redirect users after they log in.
# This MUST EXACTLY match the "Redirect URI" you set in the LoLLMs UI for this app.
REDIRECT_URI = "http://127.0.0.1:8001/sso/callback"