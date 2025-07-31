# backend/db/migration.py
import json
import re
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, IntegrityError

from backend.config import LOLLMS_CLIENT_DEFAULTS, config
from backend.db.base import CURRENT_DB_VERSION
from backend.db.models.config import GlobalConfig, LLMBinding, DatabaseVersion
from backend.db.models.service import App
from ascii_colors import ASCIIColors, trace_exception

def _bootstrap_global_settings(connection):
    """
    Ensures all necessary global settings exist in the database.
    """
    print("INFO: Checking and bootstrapping global settings in the database.")
    
    all_possible_settings = {
        "host": {
            "value": config.get("server", {}).get("host", "0.0.0.0"),
            "type": "string", "description": "Server host address. Requires a restart to take effect.", "category": "Server"
        },
        "port": {
            "value": config.get("server", {}).get("port", 9642),
            "type": "integer", "description": "Server port. Requires a restart to take effect.", "category": "Server"
        },
        "https_enabled": {
            "value": config.get("server", {}).get("https_enabled", False),
            "type": "boolean", "description": "Enable HTTPS for the server. Requires a restart to take effect.", "category": "Server"
        },
        "ssl_certfile": {
            "value": config.get("server", {}).get("ssl_certfile", ""),
            "type": "string", "description": "Path to the SSL certificate file (e.g., cert.pem). Requires a restart.", "category": "Server"
        },
        "ssl_keyfile": {
            "value": config.get("server", {}).get("ssl_keyfile", ""),
            "type": "string", "description": "Path to the SSL private key file (e.g., key.pem). Requires a restart.", "category": "Server"
        },
        "allow_new_registrations": {
            "value": config.get("app_settings", {}).get("allow_new_registrations", True),
            "type": "boolean", "description": "Allow new users to register an account.", "category": "Registration"
        },
        "registration_mode": {
            "value": config.get("app_settings", {}).get("registration_mode", "admin_approval"),
            "type": "string", "description": "Method for new user activation: 'direct' or 'admin_approval'.", "category": "Registration"
        },
        "access_token_expire_minutes": {
            "value": config.get("app_settings", {}).get("access_token_expires_mintes", 43200),
            "type": "integer", "description": "Duration in minutes a user's login session remains valid.", "category": "Authentication"
        },
        "password_recovery_mode": {
            "value": "manual",
            "type": "string", "description": "Password recovery mode: 'manual', 'automatic' (SMTP), or 'system_mail' (uses server's 'mail' command).", "category": "Authentication"
        },
        "smtp_host": {
            "value": "",
            "type": "string", "description": "SMTP server address for sending password recovery emails.", "category": "Email Settings"
        },
        "smtp_port": {
            "value": 587,
            "type": "integer", "description": "SMTP server port.", "category": "Email Settings"
        },
        "smtp_user": {
            "value": "",
            "type": "string", "description": "Username for SMTP authentication.", "category": "Email Settings"
        },
        "smtp_password": {
            "value": "",
            "type": "string", "description": "Password for SMTP authentication. (Stored in plaintext, use with caution)", "category": "Email Settings"
        },
        "smtp_from_email": {
            "value": "",
            "type": "string", "description": "The 'From' email address for password recovery emails.", "category": "Email Settings"
        },
        "smtp_use_tls": {
            "value": True,
            "type": "boolean", "description": "Use TLS for the SMTP connection.", "category": "Email Settings"
        },
        "default_lollms_model_name": {
            "value": "",
            "type": "string", "description": "Default model name assigned to newly created users.", "category": "Defaults"
        },
        "default_llm_ctx_size": {
            "value": 32000,
            "type": "integer", "description": "Default context size (in tokens) for new users.", "category": "Defaults"
        },
        "default_llm_temperature": {
            "value": 0.7,
            "type": "float", "description": "Default generation temperature for new users.", "category": "Defaults"
        },
        "default_safe_store_vectorizer": {
            "value": config.get("safe_store_defaults", {}).get("global_default_vectorizer", "st:all-MiniLM-L6-v2"),
            "type": "string", "description": "Default vectorizer assigned to newly created users.", "category": "Defaults"
        },
        "default_mcps": {
            "value": config.get("default_mcps", []),
            "type": "json", "description": "List of default Multi-Computer Protocol (MCP) tool servers.", "category": "Defaults"
        },
        "default_personalities": {
            "value": config.get("default_personas", []),
            "type": "json", "description": "List of default personalities available to all users.", "category": "Defaults"
        },
        "force_model_mode": {
            "value": "disabled",
            "type": "string", "description": "Global model override mode: 'disabled', 'force_once' (sets user pref), 'force_always' (overrides session).", "category": "Global LLM Overrides"
        },
        "force_model_name": {
            "value": "",
            "type": "string", "description": "The model name to force on all users. (e.g., 'ollama/llama3').", "category": "Global LLM Overrides"
        },
        "force_context_size": {
            "value": 4096,
            "type": "integer", "description": "The context size (in tokens) to force on all users.", "category": "Global LLM Overrides"
        },
        "openai_api_service_enabled": {
            "value": False,
            "type": "boolean", "description": "Enable the OpenAI-compatible API endpoint for users.", "category": "Services"
        }
    }

    select_keys_query = text("SELECT key FROM global_configs")
    existing_keys = {row[0] for row in connection.execute(select_keys_query).fetchall()}
    
    missing_keys = set(all_possible_settings.keys()) - existing_keys

    if not missing_keys:
        print("INFO: All global settings are already present in the database.")
        return

    print(f"INFO: Found {len(missing_keys)} missing global settings. Adding them to the database.")

    insert_stmt = GlobalConfig.__table__.insert()
    configs_to_insert = [
        {
            "key": key,
            "value": json.dumps({
                "value": all_possible_settings[key]["value"],
                "type": all_possible_settings[key]["type"]
            }),
            "description": all_possible_settings[key]["description"],
            "category": all_possible_settings[key]["category"]
        }
        for key in missing_keys
    ]

    if configs_to_insert:
        connection.execute(insert_stmt, configs_to_insert)
        print(f"INFO: Successfully bootstrapped {len(configs_to_insert)} new global settings.")

def run_schema_migrations_and_bootstrap(connection, inspector):
    if inspector.has_table("global_configs"):
        _bootstrap_global_settings(connection)

    if inspector.has_table("llm_bindings"):
        llm_bindings_columns_db = [col['name'] for col in inspector.get_columns('llm_bindings')]                        
        new_llm_bindings_cols_defs = {
            "verify_ssl_certificate": "BOOLEAN DEFAULT 1 NOT NULL"
        }
        for col_name, col_sql_def in new_llm_bindings_cols_defs.items():
            if col_name not in llm_bindings_columns_db:
                connection.execute(text(f"ALTER TABLE llm_bindings ADD COLUMN {col_name} {col_sql_def}"))
                print(f"INFO: Added missing column '{col_name}' to 'llm_bindings' table.")

    if inspector.has_table("personalities"):
        personality_columns_db = [col['name'] for col in inspector.get_columns('personalities')]
        new_personality_cols_defs = {
            "active_mcps": "JSON",
            "data_source_type": "VARCHAR DEFAULT 'none' NOT NULL",
            "data_source": "TEXT"
        }
        for col_name, col_sql_def in new_personality_cols_defs.items():
            if col_name not in personality_columns_db:
                connection.execute(text(f"ALTER TABLE personalities ADD COLUMN {col_name} {col_sql_def}"))
                print(f"INFO: Added missing column '{col_name}' to 'personalities' table.")

    if inspector.has_table("users"):
        user_columns_db = [col['name'] for col in inspector.get_columns('users')]
        
        # --- Migration from scratchpad to data_zone ---
        if 'scratchpad' in user_columns_db and 'data_zone' not in user_columns_db:
            try:
                connection.execute(text("ALTER TABLE users RENAME COLUMN scratchpad TO data_zone"))
                print("INFO: Migrated column 'users.scratchpad' to 'users.data_zone'.")
                # Refresh columns after rename
                user_columns_db = [col['name'] for col in inspector.get_columns('users')]
            except Exception as e:
                print(f"ERROR: Could not rename 'scratchpad' to 'data_zone': {e}")
        
        new_user_cols_defs = {
            "is_active": "BOOLEAN DEFAULT 1 NOT NULL", "created_at": "DATETIME", 
            "last_activity_at": "DATETIME", "activation_token": "VARCHAR",
            "password_reset_token": "VARCHAR", "reset_token_expiry": "DATETIME",
            "icon": "TEXT",
            "active_personality_id": "VARCHAR", "first_name": "VARCHAR", "family_name": "VARCHAR", 
            "email": "VARCHAR", "birth_date": "DATE", "llm_ctx_size": "INTEGER",
            "rag_top_k": "INTEGER", "max_rag_len": "INTEGER", "rag_n_hops": "INTEGER",
            "rag_min_sim_percent": "FLOAT", "rag_use_graph": "BOOLEAN DEFAULT 0",
            "rag_graph_response_type": "VARCHAR DEFAULT 'chunks_summary'",
            "put_thoughts_in_context": "BOOLEAN DEFAULT 0 NOT NULL",
            "auto_title": "BOOLEAN DEFAULT 0 NOT NULL",
            "user_ui_level":"INTEGER", "ai_response_language":"VARCHAR DEFAULT 'auto'",
            "fun_mode": "BOOLEAN DEFAULT 0 NOT NULL",
            "chat_active": "BOOLEAN DEFAULT 0 NOT NULL",
            "first_page": "VARCHAR DEFAULT 'feed' NOT NULL",
            "receive_notification_emails": "BOOLEAN DEFAULT 1 NOT NULL",
            "show_token_counter": "BOOLEAN DEFAULT 1 NOT NULL",
            "is_searchable": "BOOLEAN DEFAULT 1 NOT NULL",
            "first_login_done": "BOOLEAN DEFAULT 0 NOT NULL",
            "data_zone": "TEXT", "memory": "TEXT"
        }
        
        added_cols = []
        for col_name, col_sql_def in new_user_cols_defs.items():
            if col_name not in user_columns_db:
                try:
                    connection.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_sql_def}"))
                    print(f"INFO: Added missing column '{col_name}' to 'users' table.")
                    added_cols.append(col_name)
                except Exception as ex:
                    trace_exception(ex)

        if 'is_active' in added_cols:
            connection.execute(text("UPDATE users SET is_active = 1 WHERE is_active IS NULL"))
            print("INFO: Set 'is_active' to True for all existing users to ensure access after upgrade.")

        if 'put_thoughts_in_context' not in user_columns_db:
            try:
                connection.execute(text("UPDATE users SET put_thoughts_in_context = 0 WHERE put_thoughts_in_context IS NULL"))
                print("INFO: Set 'put_thoughts_in_context' to False for all users where it was NULL.")
            except Exception as e:
                print(f"WARNING: Could not update 'put_thoughts_in_context' to default False: {e}")

        if 'first_login_done' in added_cols:
            try:
                connection.execute(text("UPDATE users SET first_login_done = 1 WHERE first_login_done IS NULL"))
                print("INFO: Set 'first_login_done' to True for all existing users. New users will default to False.")
            except Exception as e:
                print(f"WARNING: Could not update 'first_login_done' to default True for existing users: {e}")

        user_constraints = inspector.get_unique_constraints('users')
        if 'email' in new_user_cols_defs and not any(c['name'] == 'uq_user_email' for c in user_constraints):
            try:
                connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_user_email ON users (email) WHERE email IS NOT NULL"))
                print("INFO: Created unique index 'uq_user_email' on 'users.email'.")
            except (OperationalError, IntegrityError) as e:
                print(f"Warning: Could not create unique index on email. Error: {e}")
        
        if 'password_reset_token' in new_user_cols_defs and not any(c['name'] == 'uq_password_reset_token' for c in user_constraints):
            try:
                connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_password_reset_token ON users (password_reset_token) WHERE password_reset_token IS NOT NULL"))
                print("INFO: Created unique index 'uq_password_reset_token' on 'users.password_reset_token'.")
            except (OperationalError, IntegrityError) as e:
                print(f"Warning: Could not create unique index on password_reset_token. Error: {e}")

    if inspector.has_table("mcps"):
        mcp_columns_db = [col['name'] for col in inspector.get_columns('mcps')]
        new_mcp_cols_defs = {
            "active": "BOOLEAN DEFAULT 1 NOT NULL",
            "type": "VARCHAR",
            "icon": "TEXT",
            "authentication_type": "VARCHAR", "authentication_key": "VARCHAR",
            "sso_redirect_uri": "VARCHAR", "sso_user_infos_to_share": "JSON",
            "client_id": "VARCHAR"
        }
        for col_name, col_sql_def in new_mcp_cols_defs.items():
            if col_name not in mcp_columns_db:
                connection.execute(text(f"ALTER TABLE mcps ADD COLUMN {col_name} {col_sql_def}"))
                print(f"INFO: Added missing column '{col_name}' to 'mcps' table.")

        if 'client_id' in new_mcp_cols_defs:
            mcps_to_update = connection.execute(text("SELECT id, name FROM mcps WHERE client_id IS NULL")).fetchall()
            if mcps_to_update:
                print(f"INFO: Backfilling client_id for {len(mcps_to_update)} existing MCPs...")
                
                # Defensively check for apps table and client_id column to prevent migration errors
                app_columns_db = []
                if inspector.has_table('apps'):
                    app_columns_db = [col['name'] for col in inspector.get_columns('apps')]

                for mcp_id, mcp_name in mcps_to_update:
                    base_slug = re.sub(r'[^a-z0-9_]+', '', mcp_name.lower().replace(' ', '_'))
                    new_client_id = base_slug
                    counter = 1
                    while True:
                        app_conflict = None
                        if 'client_id' in app_columns_db:
                            app_conflict = connection.execute(text("SELECT 1 FROM apps WHERE client_id = :cid"), {"cid": new_client_id}).first()
                        
                        mcp_conflict = connection.execute(text("SELECT 1 FROM mcps WHERE client_id = :cid AND id != :mid"), {"cid": new_client_id, "mid": mcp_id}).first()
                        if not app_conflict and not mcp_conflict: break
                        new_client_id = f"{base_slug}_{counter}"
                        counter += 1
                    connection.execute(text("UPDATE mcps SET client_id = :cid WHERE id = :mid"), {"cid": new_client_id, "mid": mcp_id})
                    print(f"  - Set client_id for '{mcp_name}' to '{new_client_id}'")

        mcp_constraints = inspector.get_unique_constraints('mcps')
        if 'client_id' in new_mcp_cols_defs and not any(c['name'] == 'uq_mcp_client_id' for c in mcp_constraints):
            try:
                connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_mcp_client_id ON mcps (client_id) WHERE client_id IS NOT NULL"))
                print("INFO: Created unique index 'uq_mcp_client_id' on 'mcps.client_id'.")
            except (OperationalError, IntegrityError) as e:
                print(f"Warning: Could not create unique index on mcp client_id. Error: {e}")

    if inspector.has_table("apps"):
        app_columns_db = [col['name'] for col in inspector.get_columns('apps')]
        url_col_info = next((col for col in inspector.get_columns('apps') if col['name'] == 'url'), None)

        if url_col_info and url_col_info.get('nullable') == 0:
            print("WARNING: 'url' column in 'apps' table is NOT NULL. Attempting to migrate schema...")
            try:
                connection.execute(text("PRAGMA foreign_keys=off;"))
                connection.execute(text("BEGIN TRANSACTION;"))
                connection.execute(text("ALTER TABLE apps RENAME TO _apps_old;"))
                App.__table__.create(connection)
                
                old_cols = [c['name'] for c in inspector.get_columns('_apps_old')]
                new_cols = [c['name'] for c in inspector.get_columns('apps')]
                common_cols = [c for c in old_cols if c in new_cols]
                cols_str = ", ".join(common_cols)

                connection.execute(text(f"INSERT INTO apps ({cols_str}) SELECT {cols_str} FROM _apps_old;"))
                connection.execute(text("DROP TABLE _apps_old;"))
                connection.execute(text("COMMIT;"))
                connection.execute(text("PRAGMA foreign_keys=on;"))
                print("INFO: Successfully migrated 'apps' table to make 'url' column nullable.")
            except Exception as e:
                print(f"CRITICAL: Failed to migrate 'apps' table schema. Error: {e}")
                connection.execute(text("ROLLBACK;"))
                connection.execute(text("PRAGMA foreign_keys=on;"))

        new_app_cols_defs = {
            "icon": "TEXT",
            "active": "BOOLEAN DEFAULT 1 NOT NULL",
            "type": "VARCHAR",
            "authentication_type": "VARCHAR", "authentication_key": "VARCHAR",
            "sso_redirect_uri": "VARCHAR", "sso_user_infos_to_share": "JSON",
            "client_id": "VARCHAR",
            "description": "TEXT",
            "author": "VARCHAR",
            "version": "VARCHAR",
            "category": "VARCHAR",
            "tags": "JSON",
            "is_installed": "BOOLEAN DEFAULT 0 NOT NULL",
            "status": "VARCHAR DEFAULT 'stopped' NOT NULL",
            "autostart": "BOOLEAN DEFAULT 0 NOT NULL",
            "port": "INTEGER",
            "pid": "INTEGER",
            "app_metadata": "JSON",
            "folder_name": "VARCHAR"
        }
        
        app_columns_db_after_rebuild = [col['name'] for col in inspector.get_columns('apps')]
        for col_name, col_sql_def in new_app_cols_defs.items():
            if col_name not in app_columns_db_after_rebuild:
                connection.execute(text(f"ALTER TABLE apps ADD COLUMN {col_name} {col_sql_def}"))
                print(f"INFO: Added missing column '{col_name}' to 'apps' table.")

        if 'client_id' in new_app_cols_defs:
            apps_to_update = connection.execute(text("SELECT id, name FROM apps WHERE client_id IS NULL")).fetchall()
            if apps_to_update:
                print(f"INFO: Backfilling client_id for {len(apps_to_update)} existing Apps...")
                for app_id, app_name in apps_to_update:
                    base_slug = re.sub(r'[^a-z0-9_]+', '', app_name.lower().replace(' ', '_'))
                    new_client_id = base_slug
                    counter = 1
                    while True:
                        app_conflict = connection.execute(text("SELECT 1 FROM apps WHERE client_id = :cid AND id != :aid"), {"cid": new_client_id, "aid": app_id}).first()
                        mcp_conflict = connection.execute(text("SELECT 1 FROM mcps WHERE client_id = :cid"), {"cid": new_client_id}).first()
                        if not app_conflict and not mcp_conflict: break
                        new_client_id = f"{base_slug}_{counter}"
                        counter += 1
                    connection.execute(text("UPDATE apps SET client_id = :cid WHERE id = :aid"), {"cid": new_client_id, "aid": app_id})
                    print(f"  - Set client_id for '{app_name}' to '{new_client_id}'")
        
        app_constraints = inspector.get_unique_constraints('apps')
        if 'port' in new_app_cols_defs and not any(c['name'] == 'uq_app_port' for c in app_constraints):
            try:
                connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_app_port ON apps (port) WHERE port IS NOT NULL"))
                print("INFO: Created unique index 'uq_app_port' on 'apps.port'.")
            except (OperationalError, IntegrityError) as e:
                print(f"Warning: Could not create unique index on app port. Error: {e}")
        
        if 'client_id' in new_app_cols_defs and not any(c['name'] == 'uq_app_client_id' for c in app_constraints):
            try:
                connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_app_client_id ON apps (client_id) WHERE client_id IS NOT NULL"))
                print("INFO: Created unique index 'uq_app_client_id' on 'apps.client_id'.")
            except (OperationalError, IntegrityError) as e:
                print(f"Warning: Could not create unique index on app client_id. Error: {e}")

    if inspector.has_table("system_apps"):
        system_app_columns_db = [col['name'] for col in inspector.get_columns('system_apps')]
        new_system_app_cols_defs = {
            "sso_redirect_uri": "VARCHAR", "sso_user_infos_to_share": "JSON"
        }
        for col_name, col_sql_def in new_system_app_cols_defs.items():
            if col_name not in system_app_columns_db:
                connection.execute(text(f"ALTER TABLE system_apps ADD COLUMN {col_name} {col_sql_def}"))
                print(f"INFO: Added missing column '{col_name}' to 'system_apps' table.")

def check_and_update_db_version(SessionLocal):
    session = SessionLocal()
    try:
        version_record = session.query(DatabaseVersion).filter_by(id=1).first()
        if not version_record:
            print(f"INFO: No DB version record found. Setting initial version to {CURRENT_DB_VERSION}.")
            new_version_record = DatabaseVersion(id=1, version=CURRENT_DB_VERSION)
            session.add(new_version_record)
            session.commit()
        elif version_record.version != CURRENT_DB_VERSION:
            print(f"INFO: DB version is {version_record.version}. Code expects {CURRENT_DB_VERSION}. Updating record.")
            version_record.version = CURRENT_DB_VERSION
            session.commit()
    except Exception as e_ver:
        print(f"ERROR: Could not read/update DB version: {e_ver}")
        session.rollback()
    finally:
        session.close()