# backend/db/migration.py
import json
import re
from datetime import datetime
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy.schema import DropTable
from sqlalchemy.ext.compiler import compiles

from backend.config import LOLLMS_CLIENT_DEFAULTS, config
from backend.db.base import CURRENT_DB_VERSION
from backend.db.models.config import GlobalConfig, LLMBinding, DatabaseVersion
from backend.db.models.service import App # Ensure App is imported
from backend.db.models.prompt import SavedPrompt
from backend.db.models.fun_fact import FunFactCategory, FunFact
from backend.db.models.user import User
from backend.db.models.memory import UserMemory
from ascii_colors import ASCIIColors, trace_exception


# This custom compiler allows us to drop tables with cascade in SQLite,
# though SQLAlchemy's default DROP TABLE handles foreign keys if they are defined correctly.
# Keeping this for robustness in case `drop table` implicitly needs CASCADE for some reason.
@compiles(DropTable, "sqlite")
def _drop_table(element, compiler, **kw):
    return "DROP TABLE %s;" % compiler.process(element.element)

# NEW HELPER FUNCTIONS FOR PORT UNIQUESS DURING MIGRATION
def _get_all_existing_app_ports(connection) -> set[int]:
    """Retrieves all non-null ports currently used by apps in the database."""
    # Use a direct query to avoid ORM overhead during migration and ensure we get current state
    return {r[0] for r in connection.execute(text("SELECT port FROM apps WHERE port IS NOT NULL")).fetchall()}

def _find_unique_port_for_migration(connection, preferred_port: int, already_used_in_batch: set) -> int:
    """
    Finds a unique port during migration by checking against DB and in-batch used ports.
    Starts searching from preferred_port upwards.
    """
    all_db_used_ports_at_start = _get_all_existing_app_ports(connection)
    
    current_port = preferred_port if preferred_port is not None and preferred_port >= 1024 else 9601 # Ensure valid start port
    
    while True:
        if current_port in already_used_in_batch or current_port in all_db_used_ports_at_start:
            current_port += 1
        else:
            return current_port

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
        "public_domain_name": {
            "value": "",
            "type": "string", "description": "Public domain or IP to use for links when server is on 0.0.0.0. If empty, auto-detects IP.", "category": "Server"
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
            "type": "boolean", "description": "Enable the OpenAI-compatible v1 API endpoint for users.", "category": "Services"
        },
        "openai_api_require_key": {
            "value": True,
            "type": "boolean", "description": "Require an API key for the OpenAI-compatible v1 API endpoint. If disabled, requests without a key will be handled by the primary admin account.", "category": "Services"
        },
        "ollama_service_enabled": {
            "value": False,
            "type": "boolean", "description": "Enable the Ollama service endpoint for users (OpenAI compatible).", "category": "Services"
        },
        "ollama_require_key": {
            "value": True,
            "type": "boolean", "description": "Require an API key for the Ollama service endpoint. If disabled, requests without a key will be handled by the primary admin account.", "category": "Services"
        },
        "model_display_mode": {
            "value": "mixed",
            "type": "string", "description": "How models are displayed to users: 'original' (shows raw names), 'aliased' (shows only models with aliases), 'mixed' (shows aliases where available, originals otherwise).", "category": "Models"
        },
        "tti_model_display_mode": {
            "value": "mixed",
            "type": "string", "description": "How TTI models are displayed to users: 'original' (shows raw names), 'aliased' (shows only models with aliases), 'mixed' (shows aliases where available, originals otherwise).", "category": "Models"
        },
        "lock_all_context_sizes": {
            "value": False,
            "type": "boolean", "description": "Lock context size for all aliased models, preventing users from changing it.", "category": "Models"
        },
        "ai_bot_enabled": {
            "value": False,
            "type": "boolean", "description": "Enable the @lollms AI bot to respond to mentions in the social feed.", "category": "AI Bot"
        },
        "ai_bot_binding_model": {
            "value": "",
            "type": "string", "description": "The full binding/model name for the AI bot (e.g., 'ollama/llama3').", "category": "AI Bot"
        },
        "ai_bot_personality_id": {
            "value": "",
            "type": "string", "description": "The ID of the personality to use for the bot. Overrides the system prompt if set.", "category": "AI Bot"
        },
        "ai_bot_system_prompt": {
            "value": "You are lollms, a helpful AI assistant integrated into this social platform. When a user mentions you using '@lollms', you should respond to their post helpfully and concisely. Your goal is to be a friendly and informative presence in the community.",
            "type": "text", "description": "The system prompt to use for the bot if no personality is selected.", "category": "AI Bot"
        },
        "welcome_text": {
            "value": "lollms",
            "type": "string", "description": "The main text displayed on the welcome page.", "category": "Welcome Page"
        },
        "welcome_slogan": {
            "value": "One tool to rule them all",
            "type": "string", "description": "The slogan displayed under the main text on the welcome page.", "category": "Welcome Page"
        },
        "welcome_logo_url": {
            "value": "",
            "type": "string", "description": "URL to a custom logo for the welcome page. Leave empty for default.", "category": "Welcome Page"
        },
        "latex_builder_enabled": {
            "value": False,
            "type": "boolean", "description": "Enable the LaTeX builder to compile LaTeX code blocks into PDFs.", "category": "Builders"
        },
        "latex_builder_path": {
            "value": "pdflatex",
            "type": "string", "description": "Path to the pdflatex executable. On Windows, this might be 'C:\\texlive\\2023\\bin\\win32\\pdflatex.exe'. On Linux, 'pdflatex' should suffice if it's in the system's PATH.", "category": "Builders"
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
        connection.commit()
        print(f"INFO: Successfully bootstrapped {len(configs_to_insert)} new global settings.")

def _bootstrap_fun_facts(connection):
    """
    Reads fun facts from the JSON file and populates the database if the tables are empty.
    """
    print("INFO: Checking and bootstrapping fun facts in the database.")
    
    try:
        # Check if any categories exist. If so, we assume bootstrapping is done.
        category_count = connection.execute(text("SELECT COUNT(id) FROM fun_fact_categories")).scalar_one()
        if category_count > 0:
            print("INFO: Fun facts already exist in the database. Skipping bootstrap.")
            return

        fun_facts_path = Path(__file__).parent.parent / "assets" / "fun_facts.json"
        if not fun_facts_path.exists():
            print("WARNING: fun_facts.json not found. Cannot bootstrap fun facts.")
            return

        with open(fun_facts_path, "r", encoding="utf-8") as f:
            categorized_facts = json.load(f)

        category_insert_stmt = FunFactCategory.__table__.insert()
        fact_insert_stmt = FunFact.__table__.insert()
        
        default_colors = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899"]
        color_index = 0

        for category_name, facts in categorized_facts.items():
            color = default_colors[color_index % len(default_colors)]
            color_index += 1
            
            # Insert category and get its ID
            result = connection.execute(category_insert_stmt.values(name=category_name, is_active=True, color=color))
            category_id = result.inserted_primary_key[0]
            
            facts_to_insert = [
                {"content": fact_content, "category_id": category_id}
                for fact_content in facts if fact_content.strip()
            ]
            
            if facts_to_insert:
                connection.execute(fact_insert_stmt, facts_to_insert)
        
        connection.commit()
        print(f"INFO: Successfully bootstrapped {len(categorized_facts)} categories of fun facts.")

    except Exception as e:
        print(f"CRITICAL: Failed to bootstrap fun facts. Error: {e}")
        trace_exception(e)
        connection.rollback()

def _bootstrap_lollms_user(connection):
    """
    Ensures the special @lollms user exists in the database.
    """
    # Moved imports here to prevent circular dependency during startup
    from backend.security import get_password_hash
    import secrets

    lollms_user_exists = connection.execute(text("SELECT 1 FROM users WHERE username = 'lollms'")).first()
    if not lollms_user_exists:
        print("INFO: Creating special AI user '@lollms'.")
        # Generate a secure, unusable password hash
        dummy_password = secrets.token_hex(32)
        hashed_password = get_password_hash(dummy_password)
        
        # This is a raw insert, avoiding the ORM User model to prevent potential import issues in migration scripts
        connection.execute(
            text("""
                INSERT INTO users (
                    username, hashed_password, is_admin, is_active, is_searchable, 
                    first_login_done, receive_notification_emails, is_moderator,
                    put_thoughts_in_context, auto_title, chat_active, first_page,
                    show_token_counter, rag_use_graph
                )
                VALUES (
                    :username, :hashed_password, :is_admin, :is_active, :is_searchable, 
                    :first_login_done, :receive_notification_emails, :is_moderator,
                    :put_thoughts_in_context, :auto_title, :chat_active, :first_page,
                    :show_token_counter, :rag_use_graph
                )
            """),
            {
                "username": "lollms",
                "hashed_password": hashed_password,
                "is_admin": False,
                "is_active": True,
                "is_searchable": True,
                "first_login_done": True,
                "receive_notification_emails": False,
                "is_moderator": False,
                "put_thoughts_in_context": False,
                "auto_title": False,
                "chat_active": False,
                "first_page": "feed",
                "show_token_counter": True,
                "rag_use_graph": False
            }
        )
        connection.commit()
        print("INFO: AI user '@lollms' created successfully.")
    else:
        print("INFO: AI user '@lollms' already exists.")

def run_schema_migrations_and_bootstrap(connection, inspector):
    if inspector.has_table("global_configs"):
        _bootstrap_global_settings(connection)

        # Remove deprecated settings from existing installations
        keys_to_remove_str = "('default_mcps', 'default_personalities')"
        try:
            result = connection.execute(text(f"DELETE FROM global_configs WHERE key IN {keys_to_remove_str}"))
            if result.rowcount > 0:
                print(f"INFO: Removed {result.rowcount} deprecated global settings (default_mcps, default_personalities).")
                connection.commit()
        except Exception as e:
            print(f"WARNING: Could not remove deprecated global settings. Error: {e}")
            connection.rollback()

    if inspector.has_table("tasks"):
        task_columns_db = [col['name'] for col in inspector.get_columns('tasks')]
        if 'updated_at' not in task_columns_db:
            try:
                connection.execute(text("ALTER TABLE tasks ADD COLUMN updated_at DATETIME"))
                print("INFO: Added 'updated_at' column to 'tasks' table.")
                # Backfill new column with existing created_at data
                connection.execute(text("UPDATE tasks SET updated_at = created_at WHERE updated_at IS NULL"))
                print("INFO: Backfilled 'updated_at' values from 'created_at' in 'tasks' table.")
                connection.commit()
            except Exception as e:
                print(f"ERROR: Could not add and backfill 'updated_at' column in 'tasks' table: {e}")
                connection.rollback()
                
    if inspector.has_table("saved_prompts"):
        columns_db = [col['name'] for col in inspector.get_columns('saved_prompts')]
        
        new_cols_defs = {
            "category": "VARCHAR",
            "author": "VARCHAR",
            "description": "TEXT",
            "icon": "TEXT",
            "version": "VARCHAR",
            "repository": "VARCHAR",
            "folder_name": "VARCHAR"
        }
        for col_name, col_sql_def in new_cols_defs.items():
            if col_name not in columns_db:
                connection.execute(text(f"ALTER TABLE saved_prompts ADD COLUMN {col_name} {col_sql_def}"))
                print(f"INFO: Added missing column '{col_name}' to 'saved_prompts' table.")
        connection.commit()

        full_columns_info = inspector.get_columns('saved_prompts')
        owner_user_id_col_info_full = next((col for col in full_columns_info if col['name'] == 'owner_user_id'), None)
        
        if owner_user_id_col_info_full and owner_user_id_col_info_full.get('nullable') == False:
            print("INFO: 'owner_user_id' in 'saved_prompts' needs migration. Using data-safe reset.")
            try:
                # 1. Backup data in memory
                old_cols_info = inspector.get_columns('saved_prompts')
                old_cols_names = [c['name'] for c in old_cols_info]
                data = connection.execute(text("SELECT * FROM saved_prompts")).mappings().all()
                
                # 2. Drop the old table completely
                connection.execute(text("DROP TABLE saved_prompts;"))
                print("INFO: Dropped old 'saved_prompts' table.")
                
                # 3. Recreate with new schema
                SavedPrompt.__table__.create(connection)
                print("INFO: Recreated 'saved_prompts' table with new schema.")

                # 4. Restore data
                if data:
                    new_cols_names = [c.name for c in SavedPrompt.__table__.columns]
                    restored_count = 0
                    for row in data:
                        row_data = {k: v for k, v in row.items() if k in new_cols_names}
                        connection.execute(SavedPrompt.__table__.insert().values(row_data))
                        restored_count += 1
                    print(f"INFO: Restored {restored_count} rows to 'saved_prompts' table.")
                connection.commit()
            except Exception as e:
                print(f"CRITICAL: Data-safe reset for 'saved_prompts' failed. Error: {e}")
                connection.rollback()
                raise e
            
    # Add migration for DMs if its column type changed from Integer to String
    if inspector.has_table("direct_messages"):
        direct_messages_columns_db = [col['name'] for col in inspector.get_columns('direct_messages')]
        new_direct_messages_cols_defs = {
            "image_references": "JSON",
        }
        for col_name, col_sql_def in new_direct_messages_cols_defs.items():
            if col_name not in direct_messages_columns_db:
                connection.execute(text(f"ALTER TABLE direct_messages ADD COLUMN {col_name} {col_sql_def}"))
                print(f"INFO: Added missing column '{col_name}' to 'personalities' table.")
        connection.commit()    

    # Add migration for DatabaseVersion if its column type changed from Integer to String
    if inspector.has_table("database_version"):
        db_version_cols = inspector.get_columns('database_version')
        version_col_info = next((col for col in db_version_cols if col['name'] == 'version'), None)
        
        # Check if column exists and its type is not string-like (e.g., if it's still INTEGER)
        if version_col_info and "VARCHAR" not in str(version_col_info['type']).upper() and "TEXT" not in str(version_col_info['type']).upper():
            print("INFO: 'database_version.version' column type might be incorrect. Performing data-safe table rebuild.")
            try:
                old_version_data = connection.execute(text("SELECT id, version FROM database_version")).mappings().first()
                
                connection.execute(text("DROP TABLE database_version;"))
                print("INFO: Dropped old 'database_version' table.")
                
                DatabaseVersion.__table__.create(connection)
                print("INFO: Recreated 'database_version' table with new schema.")

                if old_version_data:
                    # Attempt to convert old integer version to string if it was numeric
                    version_val = str(old_version_data['version']) if isinstance(old_version_data['version'], (int, float)) else old_version_data['version']
                    connection.execute(DatabaseVersion.__table__.insert().values(id=old_version_data['id'], version=version_val))
                    print(f"INFO: Migrated and restored version '{version_val}' to 'database_version' table.")
                connection.commit()
            except Exception as e:
                print(f"CRITICAL: Data-safe rebuild for 'database_version' table failed. Error: {e}")
                connection.rollback()
                trace_exception(e)
                raise # Re-raise to stop the application and indicate migration failure


    if inspector.has_table("llm_bindings"):
        llm_bindings_columns_db = [col['name'] for col in inspector.get_columns('llm_bindings')]
        
        # Check for deprecated columns that require a full table rebuild
        # This list includes all historical old parameters
        columns_requiring_rebuild = [
            'verify_ssl_certificate', 'host_address', 'service_key', 'models_path',
            'ctx_size', 'user_name', 'ai_name', 'temperature', 'top_k', 'top_p',
            'repeat_penalty', 'repeat_last_n'
        ]
        
        # A simpler check: if *any* of the deprecated columns exist, rebuild.
        needs_rebuild = any(col_name in llm_bindings_columns_db for col_name in columns_requiring_rebuild)

        if needs_rebuild:
            print(f"INFO: Found deprecated columns in 'llm_bindings'. Performing data-safe table rebuild.")
            
            try:
                # 1. Backup all data from old table
                # Use a plain SELECT * to get all existing columns, including deprecated ones
                data_proxy = connection.execute(text("SELECT * FROM llm_bindings"))
                column_names = data_proxy.keys()
                rows = data_proxy.fetchall()
                data_to_migrate = [dict(zip(column_names, row)) for row in rows]
                
                # 2. Disable foreign keys for the rebuild
                connection.execute(text("PRAGMA foreign_keys=off;"))
                restored_count = 0
                new_rows_data = []              
                # 5. Restore data and migrate deprecated fields into 'config'
                if data_to_migrate:
                    for row in data_to_migrate:
                        # Initialize config with existing JSON if present
                        existing_config = row.get('config')
                        if isinstance(existing_config, str):
                            try: existing_config = json.loads(existing_config)
                            except (json.JSONDecodeError, TypeError): existing_config = {}
                        elif not isinstance(existing_config, dict):
                            existing_config = {}
                        
                        # Prepare data for new 'config' JSON field from deprecated columns
                        json_to_add = {}
                        if 'verify_ssl_certificate' in row and row['verify_ssl_certificate'] is not None:
                            json_to_add['verify_ssl_certificate'] = bool(row['verify_ssl_certificate'])
                        if 'host_address' in row and row['host_address'] is not None:
                            json_to_add['host_address'] = row['host_address']
                        if 'service_key' in row and row['service_key'] is not None:
                            json_to_add['service_key'] = row['service_key']
                        if 'models_path' in row and row['models_path'] is not None:
                            json_to_add['models_path'] = row['models_path']
                        if 'ctx_size' in row and row['ctx_size'] is not None:
                            json_to_add['ctx_size'] = row['ctx_size']
                        if 'user_name' in row and row['user_name'] is not None:
                            json_to_add['user_name'] = row['user_name']
                        if 'ai_name' in row and row['ai_name'] is not None:
                            json_to_add['ai_name'] = row['ai_name']
                        if 'temperature' in row and row['temperature'] is not None:
                            json_to_add['temperature'] = row['temperature']
                        if 'top_k' in row and row['top_k'] is not None:
                            json_to_add['top_k'] = row['top_k']
                        if 'top_p' in row and row['top_p'] is not None:
                            json_to_add['top_p'] = row['top_p']
                        if 'repeat_penalty' in row and row['repeat_penalty'] is not None:
                            json_to_add['repeat_penalty'] = row['repeat_penalty']
                        if 'repeat_last_n' in row and row['repeat_last_n'] is not None:
                            json_to_add['repeat_last_n'] = row['repeat_last_n']

                        # Convert datetime strings to datetime objects for 'created_at' and 'updated_at'
                        created_at_dt = None
                        if 'created_at' in row and row['created_at'] is not None:
                            if isinstance(row['created_at'], str):
                                try: created_at_dt = datetime.fromisoformat(row['created_at'])
                                except ValueError: pass # Keep as None if parsing fails
                            else: created_at_dt = row['created_at'] # Assume it's already a datetime object

                        updated_at_dt = None
                        if 'updated_at' in row and row['updated_at'] is not None:
                            if isinstance(row['updated_at'], str):
                                try: updated_at_dt = datetime.fromisoformat(row['updated_at'])
                                except ValueError: pass # Keep as None if parsing fails
                            else: updated_at_dt = row['updated_at'] # Assume it's already a datetime object

                        # Construct the final row data for insertion into the new table
                        # Ensure all NOT NULL fields of the LLMBinding model get a value.
                        # For alias and name, they are NOT NULL, so use existing value or a fallback.
                        new_row_data = {
                            'id': row['id'],
                            'alias': row.get('alias') or row.get('name') or f"binding_{row['id']}",
                            'name': row.get('name') or row.get('alias') or f"binding_{row['id']}",
                            'config': {**existing_config, **json_to_add}, # Merged config dict
                            'default_model_name': row.get('default_model_name'),
                            'is_active': row.get('is_active', True), # Default to True if original was NULL/missing
                            'created_at': created_at_dt, # Use converted datetime object
                            'updated_at': updated_at_dt, # Use converted datetime object
                            'model_aliases': row.get('model_aliases')
                        }

                        # Only insert if alias and name are not None (should be handled by coalesce)
                        if new_row_data['alias'] is None or new_row_data['name'] is None:
                             print(f"WARNING: Skipping row {row['id']} during LLMBinding migration due to missing alias/name after fallback.")
                             continue
                        new_rows_data.append(new_row_data)
                else:
                    print("INFO: No existing data in 'llm_bindings' to migrate.")

                # 3. Drop the old table completely
                connection.execute(text("DROP TABLE llm_bindings;"))
                connection.commit()  # Commit the drop to ensure it's fully removed
                print("INFO: Dropped old 'llm_bindings' table.")

                # 4. Recreate the table from the current SQLAlchemy model definition
                # This ensures the schema (including NOT NULLs) is exactly what the model expects.
                LLMBinding.__table__.create(connection)
                print("INFO: Recreated 'llm_bindings' table from model definition.")
                for new_row_data in new_rows_data:
                    connection.execute(LLMBinding.__table__.insert().values(new_row_data))
                    restored_count += 1
                
                if restored_count > 0:
                    print(f"INFO: Migrated and restored {restored_count} rows to 'llm_bindings' table.")
                connection.commit()
            except Exception as e:
                print(f"CRITICAL: Data-safe rebuild for 'llm_bindings' table failed. Error: {e}")
                connection.rollback()
                trace_exception(e)
                raise e # Re-raise to stop the application and indicate migration failure
            finally:
                # Always re-enable foreign keys
                connection.execute(text("PRAGMA foreign_keys=on;"))

    if inspector.has_table("personalities"):
        personality_columns_db = [col['name'] for col in inspector.get_columns('personalities')]
        new_personality_cols_defs = {
            "active_mcps": "JSON",
            "data_source_type": "VARCHAR DEFAULT 'none' NOT NULL",
            "data_source": "TEXT",
            "version": "VARCHAR",
            "repository": "VARCHAR",
            "folder_name": "VARCHAR"
        }
        for col_name, col_sql_def in new_personality_cols_defs.items():
            if col_name not in personality_columns_db:
                connection.execute(text(f"ALTER TABLE personalities ADD COLUMN {col_name} {col_sql_def}"))
                print(f"INFO: Added missing column '{col_name}' to 'personalities' table.")
        connection.commit()

    if inspector.has_table("users"):
        user_columns_db = [col['name'] for col in inspector.get_columns('users')]
        
        if 'scratchpad' in user_columns_db and 'data_zone' not in user_columns_db:
            try:
                connection.execute(text("ALTER TABLE users RENAME COLUMN scratchpad TO data_zone"))
                print("INFO: Migrated column 'users.scratchpad' to 'users.data_zone'.")
                user_columns_db = [col['name'] for col in inspector.get_columns('users')]
                connection.commit()
            except Exception as e:
                print(f"ERROR: Could not rename 'scratchpad' to 'data_zone': {e}")
                connection.rollback()
        
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
            "data_zone": "TEXT", "memory": "TEXT",
            "is_moderator": "BOOLEAN DEFAULT 0 NOT NULL",
            "tti_binding_model_name": "VARCHAR",
            "tti_models_config": "JSON",
            "include_memory_date_in_context": "BOOLEAN DEFAULT 0 NOT NULL",
        }
        
        added_cols = []
        for col_name, col_sql_def in new_user_cols_defs.items():
            if col_name not in user_columns_db:
                try:
                    connection.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_sql_def}"))
                    print(f"INFO: Added missing column '{col_name}' to 'users' table.")
                    added_cols.append(col_name)
                    connection.commit()
                except Exception as ex:
                    trace_exception(ex)
                    connection.rollback()

        if 'is_active' in added_cols:
            connection.execute(text("UPDATE users SET is_active = 1 WHERE is_active IS NULL"))
            print("INFO: Set 'is_active' to True for all existing users to ensure access after upgrade.")
            connection.commit()

        if 'put_thoughts_in_context' not in user_columns_db:
            try:
                connection.execute(text("UPDATE users SET put_thoughts_in_context = 0 WHERE put_thoughts_in_context IS NULL"))
                print("INFO: Set 'put_thoughts_in_context' to False for all users where it was NULL.")
                connection.commit()
            except Exception as e:
                print(f"WARNING: Could not update 'put_thoughts_in_context' to default False: {e}")
                connection.rollback()

        if 'first_login_done' in added_cols:
            try:
                connection.execute(text("UPDATE users SET first_login_done = 1 WHERE first_login_done IS NULL"))
                print("INFO: Set 'first_login_done' to True for all existing users. New users will default to False.")
                connection.commit()
            except Exception as e:
                print(f"WARNING: Could not update 'first_login_done' to default True for existing users: {e}")
                connection.rollback()

        user_constraints = inspector.get_unique_constraints('users')
        if 'email' in new_user_cols_defs and not any(c['name'] == 'uq_user_email' for c in user_constraints):
            try:
                connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_user_email ON users (email) WHERE email IS NOT NULL"))
                print("INFO: Created unique index 'uq_user_email' on 'users.email'.")
                connection.commit()
            except (OperationalError, IntegrityError) as e:
                print(f"Warning: Could not create unique index on email. Error: {e}")
                connection.rollback()
        
        if 'password_reset_token' in new_user_cols_defs and not any(c['name'] == 'uq_password_reset_token' for c in user_constraints):
            try:
                connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_password_reset_token ON users (password_reset_token) WHERE password_reset_token IS NOT NULL"))
                print("INFO: Created unique index 'uq_password_reset_token' on 'users.password_reset_token'.")
                connection.commit()
            except (OperationalError, IntegrityError) as e:
                print(f"Warning: Could not create unique index on password_reset_token. Error: {e}")
                connection.rollback()
        
    # NEW: Migration for posts.visibility case issue
    if inspector.has_table("posts"):
        try:
            # This query will only update rows where visibility is not already lowercase.
            # It's safe to run multiple times.
            result = connection.execute(text("UPDATE posts SET visibility = LOWER(visibility) WHERE visibility != LOWER(visibility)"))
            if result.rowcount > 0:
                print(f"INFO: Migrated {result.rowcount} post visibility values to lowercase.")
                connection.commit()
        except Exception as e:
            print(f"WARNING: Could not run migration for 'posts.visibility' column. Error: {e}")
            connection.rollback()


    if not inspector.has_table("user_memories"):
        UserMemory.__table__.create(connection)
        print("INFO: Created 'user_memories' table.")
        connection.commit()
    else:
        # Migration for owner_user_id column if it's missing
        user_memories_columns = [col['name'] for col in inspector.get_columns('user_memories')]
        if 'owner_user_id' not in user_memories_columns:
            try:
                # Add the column, making it nullable temporarily for existing data
                connection.execute(text("ALTER TABLE user_memories ADD COLUMN owner_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE"))
                print("INFO: Added 'owner_user_id' column to 'user_memories' table.")
                
                # Assign existing memories to the primary admin (user_id=1) as a fallback.
                admin_user = connection.execute(text("SELECT id FROM users WHERE is_admin = 1 ORDER BY id ASC LIMIT 1")).first()
                if admin_user:
                    connection.execute(text(f"UPDATE user_memories SET owner_user_id = {admin_user[0]} WHERE owner_user_id IS NULL"))
                    print(f"INFO: Assigned existing orphan memories to primary admin (user_id={admin_user[0]}).")
                
                connection.commit()
            except Exception as e:
                print(f"ERROR: Could not add and backfill 'owner_user_id' column in 'user_memories' table: {e}")
                connection.rollback()
        
        if 'updated_at' not in user_memories_columns:
            try:
                connection.execute(text("ALTER TABLE user_memories ADD COLUMN updated_at DATETIME"))
                print("INFO: Added 'updated_at' column to 'user_memories' table.")
                # Backfill with created_at values
                connection.execute(text("UPDATE user_memories SET updated_at = created_at WHERE updated_at IS NULL"))
                print("INFO: Backfilled 'updated_at' values in 'user_memories' table.")
                connection.commit()
            except Exception as e:
                print(f"ERROR: Could not add and backfill 'updated_at' column in 'user_memories' table: {e}")
                connection.rollback()

        # Cleanup for existing empty memories
        try:
            result = connection.execute(text("DELETE FROM user_memories WHERE title IS NULL OR title = '' OR content IS NULL OR content = ''"))
            if result.rowcount > 0:
                print(f"INFO: Cleaned up {result.rowcount} empty or invalid memories from the database.")
                connection.commit()
        except Exception as e:
            print(f"WARNING: Could not run cleanup for empty memories. Error: {e}")
            connection.rollback()

    _bootstrap_lollms_user(connection)

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
        connection.commit()
        
        if 'client_id' in new_mcp_cols_defs:
            mcps_to_update = connection.execute(text("SELECT id, name FROM mcps WHERE client_id IS NULL")).fetchall()
            if mcps_to_update:
                print(f"INFO: Backfilling client_id for {len(mcps_to_update)} existing MCPs...")
                
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
                connection.commit()

        mcp_constraints = inspector.get_unique_constraints('mcps')
        if 'client_id' in new_mcp_cols_defs and not any(c['name'] == 'uq_mcp_client_id' for c in mcp_constraints):
            try:
                connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_mcp_client_id ON mcps (client_id) WHERE client_id IS NOT NULL"))
                print("INFO: Created unique index 'uq_mcp_client_id' on 'mcps.client_id'.")
                connection.commit()
            except (OperationalError, IntegrityError) as e:
                print(f"Warning: Could not create unique index on mcp client_id. Error: {e}")
                connection.rollback()

    if inspector.has_table("apps"):
        app_columns_db = [col['name'] for col in inspector.get_columns('apps')]
        url_col_info = next((col for col in inspector.get_columns('apps') if col['name'] == 'url'), None)

        if url_col_info and url_col_info.get('nullable') == 0:
            print("WARNING: 'url' column in 'apps' table is NOT NULL or other schema changes detected. Attempting to migrate schema using data-safe reset.")
            try:
                # 1. Backup data in memory
                data = connection.execute(text("SELECT * FROM apps")).mappings().all()
                
                # 2. Drop the old table completely
                connection.execute(text("DROP TABLE apps;"))
                print("INFO: Dropped old 'apps' table.")
                
                # 3. Recreate with new schema (this will apply unique=True on port)
                App.__table__.create(connection)
                print("INFO: Recreated 'apps' table with new schema.")

                # 4. Restore data, handling port uniqueness
                if data:
                    new_cols_names = [c.name for c in App.__table__.columns]
                    restored_count = 0
                    used_ports_during_migration_batch = set() # Track ports assigned during this migration batch
                    
                    for row in data:
                        row_data = {k: v for k, v in row.items() if k in new_cols_names}
                        
                        # FIX: Convert string timestamps to datetime objects
                        if 'created_at' in row_data and isinstance(row_data['created_at'], str):
                            try: row_data['created_at'] = datetime.fromisoformat(row_data['created_at'])
                            except ValueError: row_data['created_at'] = None
                        
                        if 'updated_at' in row_data and isinstance(row_data['updated_at'], str):
                            try: row_data['updated_at'] = datetime.fromisoformat(row_data['updated_at'])
                            except ValueError: row_data['updated_at'] = None
                        
                        # Handle port uniqueness during re-insertion
                        if 'port' in row_data and row_data['port'] is not None:
                            original_port = row_data['port']
                            new_port = _find_unique_port_for_migration(connection, original_port, used_ports_during_migration_batch)
                            if new_port != original_port:
                                print(f"  - WARNING: Port {original_port} conflict for app '{row_data.get('name', row_data['id'])}'. Reassigning to {new_port}.")
                            row_data['port'] = new_port
                            used_ports_during_migration_batch.add(new_port)
                        
                        # Backfill client_id if missing (ensure it's unique across apps and mcps)
                        if 'client_id' not in row_data or row_data['client_id'] is None:
                            base_slug = re.sub(r'[^a-z0-9_]+', '', (row_data.get('name', 'app')).lower().replace(' ', '_'))
                            new_client_id = base_slug
                            counter = 1
                            while True:
                                # Check uniqueness across both apps and mcps tables
                                app_conflict = connection.execute(text("SELECT 1 FROM apps WHERE client_id = :cid"), {"cid": new_client_id}).first()
                                mcp_conflict = connection.execute(text("SELECT 1 FROM mcps WHERE client_id = :cid"), {"cid": new_client_id}).first()
                                if not app_conflict and not mcp_conflict: break
                                new_client_id = f"{base_slug}_{counter}"
                                counter += 1
                            row_data['client_id'] = new_client_id
                            print(f"  - Backfilled client_id for '{row_data.get('name', row_data['id'])}' to '{new_client_id}' during rebuild.")

                        connection.execute(App.__table__.insert().values(row_data))
                        restored_count += 1
                    print(f"INFO: Restored {restored_count} rows to 'apps' table.")
                connection.commit()
            except Exception as e:
                print(f"CRITICAL: Data-safe reset for 'apps' table failed. Error: {e}")
                connection.rollback()
                trace_exception(e)
                raise e

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
            "folder_name": "VARCHAR",
            "allow_openai_api_access": "BOOLEAN DEFAULT 0 NOT NULL"
        }
        
        app_columns_db_after_rebuild = [col['name'] for col in inspector.get_columns('apps')]
        for col_name, col_sql_def in new_app_cols_defs.items():
            if col_name not in app_columns_db_after_rebuild:
                connection.execute(text(f"ALTER TABLE apps ADD COLUMN {col_name} {col_sql_def}"))
                print(f"INFO: Added missing column '{col_name}' to 'apps' table.")
        connection.commit()

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
                connection.commit()
        
        app_constraints = inspector.get_unique_constraints('apps')
        if 'port' in new_app_cols_defs and not any(c['name'] == 'uq_app_port' for c in app_constraints):
            try:
                connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_app_port ON apps (port) WHERE port IS NOT NULL"))
                print("INFO: Created unique index 'uq_app_port' on 'apps.port'.")
                connection.commit()
            except (OperationalError, IntegrityError) as e:
                print(f"Warning: Could not create unique index on app port. Error: {e}")
                connection.rollback()
        
        if 'client_id' in new_app_cols_defs and not any(c['name'] == 'uq_app_client_id' for c in app_constraints):
            try:
                connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_app_client_id ON apps (client_id) WHERE client_id IS NOT NULL"))
                print("INFO: Created unique index 'uq_app_client_id' on 'apps.client_id'.")
                connection.commit()
            except (OperationalError, IntegrityError) as e:
                print(f"Warning: Could not create unique index on app client_id. Error: {e}")
                connection.rollback()

    if inspector.has_table("system_apps"):
        system_app_columns_db = [col['name'] for col in inspector.get_columns('system_apps')]
        new_system_app_cols_defs = {
            "sso_redirect_uri": "VARCHAR", "sso_user_infos_to_share": "JSON"
        }
        for col_name, col_sql_def in new_system_app_cols_defs.items():
            if col_name not in system_app_columns_db:
                connection.execute(text(f"ALTER TABLE system_apps ADD COLUMN {col_name} {col_sql_def}"))
                print(f"INFO: Added missing column '{col_name}' to 'system_apps' table.")
        connection.commit()

    if inspector.has_table("app_zoo_repositories"):
        columns_db = [col['name'] for col in inspector.get_columns('app_zoo_repositories')]
        if 'is_deletable' not in columns_db:
            connection.execute(text("ALTER TABLE app_zoo_repositories ADD COLUMN is_deletable BOOLEAN DEFAULT 1 NOT NULL"))
            print("INFO: Added 'is_deletable' column to 'app_zoo_repositories' table.")
        if 'type' not in columns_db:
            connection.execute(text("ALTER TABLE app_zoo_repositories ADD COLUMN type VARCHAR DEFAULT 'git' NOT NULL"))
            print("INFO: Added 'type' column to 'app_zoo_repositories' table.")
        connection.commit()

    if inspector.has_table("mcp_zoo_repositories"):
        columns_db = [col['name'] for col in inspector.get_columns('mcp_zoo_repositories')]
        if 'is_deletable' not in columns_db:
            connection.execute(text("ALTER TABLE mcp_zoo_repositories ADD COLUMN is_deletable BOOLEAN DEFAULT 1 NOT NULL"))
            print("INFO: Added 'is_deletable' column to 'mcp_zoo_repositories' table.")
        if 'type' not in columns_db:
            connection.execute(text("ALTER TABLE mcp_zoo_repositories ADD COLUMN type VARCHAR DEFAULT 'git' NOT NULL"))
            print("INFO: Added 'type' column to 'mcp_zoo_repositories' table.")
        connection.commit()

    if inspector.has_table("prompt_zoo_repositories"):
        columns_db = [col['name'] for col in inspector.get_columns('prompt_zoo_repositories')]
        if 'is_deletable' not in columns_db:
            connection.execute(text("ALTER TABLE prompt_zoo_repositories ADD COLUMN is_deletable BOOLEAN DEFAULT 1 NOT NULL"))
            print("INFO: Added 'is_deletable' column to 'prompt_zoo_repositories' table.")
        if 'type' not in columns_db:
            connection.execute(text(f"ALTER TABLE prompt_zoo_repositories ADD COLUMN type VARCHAR DEFAULT 'git' NOT NULL"))
            print("INFO: Added 'type' column to 'prompt_zoo_repositories' table.")
        connection.commit()
    
    # NEW: Create personality_zoo_repositories if it doesn't exist
    if not inspector.has_table("personality_zoo_repositories"):
        from backend.db.models.service import PersonalityZooRepository
        PersonalityZooRepository.__table__.create(connection)
        print("INFO: Created 'personality_zoo_repositories' table.")
        connection.commit()

    # NEW: Create broadcast_messages if it doesn't exist
    if not inspector.has_table("broadcast_messages"):
        from backend.db.models.broadcast import BroadcastMessage
        BroadcastMessage.__table__.create(connection)
        print("INFO: Created 'broadcast_messages' table for multi-worker communication.")
        connection.commit()

    # NEW: Create shared_discussion_links if it doesn't exist
    if not inspector.has_table("shared_discussion_links"):
        from backend.db.models.discussion import SharedDiscussionLink
        SharedDiscussionLink.__table__.create(connection)
        print("INFO: Created 'shared_discussion_links' table for discussion sharing.")
        connection.commit()

    if inspector.has_table("fun_fact_categories"):
        fun_fact_cat_cols = [col['name'] for col in inspector.get_columns('fun_fact_categories')]
        if 'color' not in fun_fact_cat_cols:
            connection.execute(text("ALTER TABLE fun_fact_categories ADD COLUMN color VARCHAR(7) DEFAULT '#4299e1' NOT NULL"))
            print("INFO: Added 'color' column to 'fun_fact_categories' table.")
            connection.commit()

    # NEW: Create fun_fact tables if they don't exist
    if not inspector.has_table("fun_fact_categories"):
        FunFactCategory.__table__.create(connection)
        print("INFO: Created 'fun_fact_categories' table.")
    
    if not inspector.has_table("fun_facts"):
        FunFact.__table__.create(connection)
        print("INFO: Created 'fun_facts' table.")

    # NEW: Bootstrap fun facts after tables are ensured
    if inspector.has_table("fun_fact_categories"):
        _bootstrap_fun_facts(connection)


def check_and_update_db_version(SessionLocal):
    session = SessionLocal()
    try:
        version_record = session.query(DatabaseVersion).filter_by(id=1).first()
        if not version_record:
            print(f"INFO: No DB version record found. Setting initial version to {CURRENT_DB_VERSION}.")
            # Store CURRENT_DB_VERSION as string
            new_version_record = DatabaseVersion(id=1, version=CURRENT_DB_VERSION) 
            session.add(new_version_record)
            session.commit()
        # Compare as strings
        elif version_record.version != CURRENT_DB_VERSION: 
            print(f"INFO: DB version is {version_record.version}. Code expects {CURRENT_DB_VERSION}. Updating record.")
            # Update to new string version
            version_record.version = CURRENT_DB_VERSION 
            session.commit()
    except Exception as e_ver:
        print(f"ERROR: Could not read/update DB version: {e_ver}")
        session.rollback()
    finally:
        session.close()