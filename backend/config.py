# backend/config.py
import os
import shutil
from pathlib import Path
import toml

# --- Application Version ---
APP_VERSION = "1.6.0"

# --- Configuration Loading ---
CONFIG_PATH = Path("config.toml") # Assuming config.toml is in project_root
if not CONFIG_PATH.exists():
    EXAMPLE_CONFIG_PATH = Path("config_example.toml") # Assuming config_example.toml is in project_root
    if EXAMPLE_CONFIG_PATH.exists():
        shutil.copy(EXAMPLE_CONFIG_PATH, CONFIG_PATH)
        print(f"INFO: config.toml not found. Copied from {EXAMPLE_CONFIG_PATH}.")
    else:
        print("CRITICAL: config.toml not found and config_example.toml also missing.")
        config_data = {} # Use 'config_data' to avoid conflict with module name
else:
    try:
        config_data = toml.load(CONFIG_PATH)
    except toml.TomlDecodeError as e:
        print(f"CRITICAL: Error parsing config.toml: {e}.")
        config_data = {}

APP_SETTINGS = config_data.get("app_settings", {})
APP_DATA_DIR = Path(APP_SETTINGS.get("data_dir", "data")).resolve() # Resolves relative to where script is run
# If running from backend/, this needs to be ../data
# For simplicity, assume data is relative to project root if config.toml is at root.
# If data dir should always be inside backend/, change to:
# APP_DATA_DIR = Path(__file__).parent.parent / APP_SETTINGS.get("data_dir", "data")
# However, the original code implies data is relative to project root where main.py was.
# So, Path("data") or Path("../data") from backend/ if config.toml specifies "data"
# Let's assume data is at project root level for now.

# Adjust APP_DATA_DIR if it's specified relative to the config file location
# or if it should be explicitly inside the project root.
# If config.toml defines "data", and script runs from backend/, this would be backend/data/
# If you want project_root/data, use:
# APP_DATA_DIR = CONFIG_PATH.parent / APP_SETTINGS.get("data_dir", "data")
# Assuming data directory is sibling to backend/ or as specified from project root:
_project_root = Path(__file__).parent.parent # backend/.. -> project_root
APP_DATA_DIR = _project_root / APP_SETTINGS.get("data_dir", "data")
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)


APP_DB_URL = APP_SETTINGS.get("database_url", f"sqlite:///{APP_DATA_DIR / 'app_main.db'}")
LOLLMS_CLIENT_DEFAULTS = config_data.get("lollms_client_defaults", {})
SAFE_STORE_DEFAULTS = config_data.get("safe_store_defaults", {})
INITIAL_ADMIN_USER_CONFIG = config_data.get("initial_admin_user", {})
SERVER_CONFIG = config_data.get("server", {})
DEFAULT_RAG_TOP_K = SAFE_STORE_DEFAULTS.get("default_top_k", 3)

# --- Constants ---
TEMP_UPLOADS_DIR_NAME = "temp_uploads"
DISCUSSION_ASSETS_DIR_NAME = "discussion_assets"
DATASTORES_DIR_NAME = "safestores"
PROMPT_CATEGORIES_DEFAULT = ["General", "Coding", "Writing", "Analysis", "Creative", "Roleplay", "Education", "Custom"]

MAX_IMAGE_SIZE_MB = 10
MAX_IMAGE_UPLOADS_PER_MESSAGE = 5

# Path for static files served from root (index.html, admin.html etc.)
STATIC_FILES_PATH = _project_root
LOCALES_PATH = _project_root / "locales"