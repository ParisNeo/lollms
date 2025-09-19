# backend/config.py
# Standard Library Imports
import os
import shutil
from pathlib import Path
import toml
from dotenv import load_dotenv
from multiprocessing import cpu_count

# --- Helper Function for Type Casting ---
def get_env_var(key, default, cast_type=str):
    """Gets an environment variable and casts it to the desired type."""
    value = os.environ.get(key, default)
    try:
        if cast_type == bool:
            if isinstance(value, bool):
                return value
            return str(value).lower() in ('true', '1', 'yes', 'on')
        if cast_type == int and value is not None:
            return int(value)
        return cast_type(value) if value is not None else default
    except (ValueError, TypeError):
        return default

# --- Project Root ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --- One-Time Migration from config.toml to .env ---
def _migrate_toml_to_env_if_needed():
    """
    Checks for a config.toml file and migrates its settings to a new .env file
    if .env doesn't already exist.
    """
    toml_path = PROJECT_ROOT / "config.toml"
    env_path = PROJECT_ROOT / ".env"
    
    if not env_path.exists() and toml_path.exists():
        print("INFO: Found config.toml. Migrating settings to .env file...")
        try:
            config = toml.load(toml_path)
            env_lines = [
                "# This file was automatically migrated from config.toml",
                "# Please review and update these settings as needed."
            ]
            
            # Helper to process a section
            def process_section(section_name, prefix, defaults={}):
                if section_name in config:
                    env_lines.append(f"\n# {section_name.replace('_', ' ').title()} Settings")
                    for key, value in config[section_name].items():
                        env_key = f"{prefix}_{key.upper()}"
                        env_lines.append(f"{env_key}={value}")

            process_section("server", "SERVER")
            process_section("app_settings", "APP")
            process_section("initial_admin_user", "INITIAL_ADMIN")
            process_section("lollms_client_defaults", "DEFAULT")
            process_section("safe_store_defaults", "SAFESTORE")
            process_section("redis", "REDIS")

            with open(env_path, "w", encoding="utf-8") as f:
                f.write("\n".join(env_lines))
            
            # Rename the old config file to prevent re-migration
            toml_path.rename(toml_path.with_suffix('.toml.migrated'))
            
            print("INFO: Migration successful. 'config.toml' has been renamed to 'config.toml.migrated'.")
            print("INFO: The application will now use the new '.env' file.")

        except Exception as e:
            print(f"CRITICAL: Failed to migrate config.toml to .env file. Error: {e}")

# --- Load Environment Variables ---
_migrate_toml_to_env_if_needed()
load_dotenv()

# --- Application Version ---
APP_VERSION = "1.7.0"
LOCALS_DIR = PROJECT_ROOT / "frontend" / "webui" / "public" / "locals"

# --- Configuration Loading from Environment ---
# Server settings
SERVER_CONFIG = {
    "host": get_env_var("SERVER_HOST", "0.0.0.0"),
    "port": get_env_var("SERVER_PORT", 9642, int),
    "workers": get_env_var("SERVER_WORKERS", cpu_count(), int),
    "debug": get_env_var("SERVER_DEBUG", False, bool),
    "https_enabled": get_env_var("HTTPS_ENABLED", False, bool),
    "ssl_certfile": get_env_var("SSL_CERTFILE", ""),
    "ssl_keyfile": get_env_var("SSL_KEYFILE", ""),
}

# App settings
APP_DATA_DIR = PROJECT_ROOT / get_env_var("APP_DATA_DIR", "data")
APP_DATA_DIR.mkdir(exist_ok=True, parents=True)

DATABASE_URL_CONFIG_KEY = "database_url"
APP_DB_URL = get_env_var("DATABASE_URL", f"sqlite:///{APP_DATA_DIR / 'app_main.db'}")
SECRET_KEY = get_env_var("SECRET_KEY", "a_very_secret_key_that_should_be_changed_for_production")

APP_SETTINGS = {
    "data_dir": str(APP_DATA_DIR),
    "database_url": APP_DB_URL,
    "secret_key": SECRET_KEY,
    "access_token_expires_minutes": get_env_var("ACCESS_TOKEN_EXPIRES_MINUTES", 44640, int),
    "allow_new_registrations": get_env_var("ALLOW_NEW_REGISTRATIONS", True, bool),
    "registration_mode": get_env_var("REGISTRATION_MODE", "admin_approval"),
    "public_domain_name": get_env_var("PUBLIC_DOMAIN_NAME", "")
}

# Default initial user, binding, and SafeStore settings
INITIAL_ADMIN_USER_CONFIG = {
    "username": get_env_var("INITIAL_ADMIN_USERNAME", "admin"),
    "password": get_env_var("INITIAL_ADMIN_PASSWORD", "admin")
}

LOLLMS_CLIENT_DEFAULTS = {
    "binding_name": get_env_var("DEFAULT_BINDING_NAME", "llamacpp"),
    "default_model_name": get_env_var("DEFAULT_MODEL_NAME", "llava-v1.6-mistral-7b.Q3_K_XS.gguf")
}

SAFE_STORE_DEFAULTS = {
    "cache_folder": get_env_var("SAFESTORE_CACHE_FOLDER", "data/cache/safestore"),
    "chunk_size": get_env_var("SAFESTORE_CHUNK_SIZE", 2096, int),
    "chunk_overlap": get_env_var("SAFESTORE_CHUNK_OVERLAP", 150, int),
    "global_default_vectorizer": get_env_var("SAFESTORE_GLOBAL_DEFAULT_VECTORIZER", "st:all-MiniLM-L6-v2"),
    "encryption_key": get_env_var("SAFESTORE_ENCRYPTION_KEY", "my_super_secret_safe_store_key_CHANGE_ME")
}

# --- Constants for directory names ---
TEMP_UPLOADS_DIR_NAME = "temp_uploads"
DISCUSSION_ASSETS_DIR_NAME = "discussion_assets"
DM_ASSETS_DIR_NAME = "dm_assets"
DATASTORES_DIR_NAME = "safestores"
APPS_DIR_NAME = "apps"
MCPS_DIR_NAME = "mcps"
CUSTOM_APPS_DIR_NAME = "custom_apps"
ZOO_DIR_NAME = "zoo"
MCP_ZOO_DIR_NAME = "mcps_zoo"
APPS_ZOO_DIR_NAME = "apps_zoo"
PROMPTS_ZOO_DIR_NAME = "prompts_zoo"
PERSONALITIES_ZOO_DIR_NAME = "personalities_zoo"

# --- Full Path Constants ---
APPS_ZOO_ROOT_PATH= APP_DATA_DIR / APPS_ZOO_DIR_NAME
MCPS_ZOO_ROOT_PATH = APP_DATA_DIR / MCP_ZOO_DIR_NAME
PROMPTS_ZOO_ROOT_PATH = APP_DATA_DIR / PROMPTS_ZOO_DIR_NAME
PERSONALITIES_ZOO_ROOT_PATH = APP_DATA_DIR / PERSONALITIES_ZOO_DIR_NAME
APPS_ROOT_PATH = APP_DATA_DIR / APPS_DIR_NAME
MCPS_ROOT_PATH = APP_DATA_DIR / MCPS_DIR_NAME
CUSTOM_APPS_ROOT_PATH = APP_DATA_DIR / CUSTOM_APPS_DIR_NAME

MCPS_ZOO_ROOT_PATH.mkdir(exist_ok=True, parents=True)
APPS_ROOT_PATH.mkdir(exist_ok=True, parents=True)
PROMPTS_ZOO_ROOT_PATH.mkdir(exist_ok=True, parents=True)
PERSONALITIES_ZOO_ROOT_PATH.mkdir(exist_ok=True, parents=True)

# --- Security Constants (Not moved to DB) ---
ALGORITHM = "HS256"
# SECRET_KEY is already defined above