# config.py
# Standard Library Imports
import os
import shutil
from pathlib import Path

# Third-Party Imports
import toml

# --- Application Version ---
APP_VERSION = "1.6.0"
PROJECT_ROOT = Path(__file__).resolve().parent.parent 
LOCALS_DIR = PROJECT_ROOT / "frontend" / "webui" / "public" / "locals"

# --- Configuration Loading ---
# This section remains critical for the initial bootstrap. The values from this
# file will be used to populate the `global_configs` table in the database
# on the very first run. After that, the application will read these values
# from the database via the new `backend.settings` module.
CONFIG_PATH = Path("config.toml")
if not CONFIG_PATH.exists():
    EXAMPLE_CONFIG_PATH = Path("config_example.toml")
    if EXAMPLE_CONFIG_PATH.exists():
        shutil.copy(EXAMPLE_CONFIG_PATH, CONFIG_PATH)
        print(f"INFO: config.toml not found. Copied from {EXAMPLE_CONFIG_PATH}.")
    else:
        print(
            "CRITICAL: config.toml not found and config_example.toml also missing. "
            "Please create config.toml from the example or documentation."
        )
        config = {}
else:
    try:
        config = toml.load(CONFIG_PATH)
    except toml.TomlDecodeError as e:
        print(
            f"CRITICAL: Error parsing config.toml: {e}. Please check the file for syntax errors."
        )
        config = {}

DATABASE_URL_CONFIG_KEY = "database_url"

APP_SETTINGS = config.get("app_settings", {})
APP_DATA_DIR = Path(APP_SETTINGS.get("data_dir", "data")).resolve()
APP_DB_URL = APP_SETTINGS.get(DATABASE_URL_CONFIG_KEY, f"sqlite:///{APP_DATA_DIR / 'app_main.db'}")

LOLLMS_CLIENT_DEFAULTS = config.get("lollms_client_defaults", {})
SAFE_STORE_DEFAULTS = config.get("safe_store_defaults", {})
INITIAL_ADMIN_USER_CONFIG = config.get("initial_admin_user", {})
SERVER_CONFIG = config.get("server", {})

# --- Constants for directory names ---
TEMP_UPLOADS_DIR_NAME = "temp_uploads"
DISCUSSION_ASSETS_DIR_NAME = "discussion_assets"
DATASTORES_DIR_NAME = "safestores"
APPS_DIR_NAME = "apps"
CUSTOM_APPS_DIR_NAME = "custom_apps"
ZOO_DIR_NAME = "zoo"


# --- Security Constants (Not moved to DB) ---
# These are fundamental to the application's security posture and should
# remain configured via environment or a secure file, not a dynamic DB setting.
ALGORITHM = "HS256"
SECRET_KEY = APP_SETTINGS.get("secret_key", os.environ.get("LOLLMS_SECRET_KEY", "a_very_secret_key_that_should_be_changed_for_production"))

# --- REMOVED: ACCESS_TOKEN_EXPIRE_MINUTES ---
# This value is now managed in the database via the GlobalConfig table.
# It is bootstrapped from config.toml by `database_setup.py`.
#
# Example of settings to have in your config.toml under [app_settings]:
# allow_new_registrations = true
# registration_mode = "admin_approval"  # options: "direct", "admin_approval"
# access_token_expire_minutes = 43200   # 30 days in minutes

DEFAULT_PERSONALITIES = config.get("default_personas", {})
DEFAULT_MCPS = config.get("default_mcps", [])