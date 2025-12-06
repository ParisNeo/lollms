import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy.schema import DropTable
from sqlalchemy.ext.compiler import compiles

from backend.config import SERVER_CONFIG, APP_SETTINGS, SAFE_STORE_DEFAULTS, APP_DATA_DIR, USERS_DIR_NAME
from backend.db.base import CURRENT_DB_VERSION
from backend.db.models.config import GlobalConfig, LLMBinding, TTIBinding, TTSBinding, DatabaseVersion, RAGBinding, STTBinding
from backend.db.models.service import App 
from backend.db.models.prompt import SavedPrompt
from backend.db.models.fun_fact import FunFactCategory, FunFact
from backend.db.models.user import User
from backend.db.models.group import Group
from backend.db.models.memory import UserMemory
from backend.db.models.connections import WebSocketConnection
from backend.db.models.image import UserImage
from backend.db.models.dm import Conversation, ConversationMember, DirectMessage
from backend.db.models.note import Note, NoteGroup
from ascii_colors import ASCIIColors, trace_exception


@compiles(DropTable, "sqlite")
def _drop_table(element, compiler, **kw):
    return "DROP TABLE %s;" % compiler.process(element.element)

def _get_all_existing_app_ports(connection) -> set[int]:
    """Retrieves all non-null ports currently used by apps in the database."""
    return {r[0] for r in connection.execute(text("SELECT port FROM apps WHERE port IS NOT NULL")).fetchall()}

def _find_unique_port_for_migration(connection, preferred_port: int, already_used_in_batch: set) -> int:
    """
    Finds a unique port during migration by checking against DB and in-batch used ports.
    Starts searching from preferred_port upwards.
    """
    all_db_used_ports_at_start = _get_all_existing_app_ports(connection)
    current_port = preferred_port if preferred_port is not None and preferred_port >= 1024 else 9601 
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
        "host": { "value": SERVER_CONFIG.get("host", "0.0.0.0"), "type": "string", "description": "Server host address. Requires a restart to take effect.", "category": "Server" },
        "port": { "value": SERVER_CONFIG.get("port", 9642), "type": "integer", "description": "Server port. Requires a restart to take effect.", "category": "Server" },
        "https_enabled": { "value": SERVER_CONFIG.get("https_enabled", False), "type": "boolean", "description": "Enable HTTPS for the server. Requires a restart to take effect.", "category": "Server" },
        "ssl_certfile": { "value": SERVER_CONFIG.get("ssl_certfile", ""), "type": "string", "description": "Path to the SSL certificate file (e.g., cert.pem). Requires a restart.", "category": "Server" },
        "ssl_keyfile": { "value": SERVER_CONFIG.get("ssl_keyfile", ""), "type": "string", "description": "Path to the SSL private key file (e.g., key.pem). Requires a restart.", "category": "Server" },
        "public_domain_name": { "value": APP_SETTINGS.get("public_domain_name", ""), "type": "string", "description": "Public domain or IP to use for links when server is on 0.0.0.0. If empty, auto-detects IP.", "category": "Server" },
        "cors_origins_exceptions": { "value": "", "type": "string", "description": "A comma-separated list of additional origins to allow for CORS (e.g., http://localhost:8000,https://my-app.com). Requires restart.", "category": "Server" },
        "data_path": { "value": str(APP_DATA_DIR.resolve()), "type": "string", "description": "The root directory for all application data.", "category": "Server" },
        "huggingface_cache_path": { "value": str((APP_DATA_DIR / "huggingface_cache").resolve()), "type": "string", "description": "Path for Hugging Face model cache. Requires a restart to change.", "category": "Server" },
        "backup_password": { "value": "", "type": "string", "description": "Password to encrypt application backups.", "category": "Backup" },
        "allow_new_registrations": { "value": APP_SETTINGS.get("allow_new_registrations", True), "type": "boolean", "description": "Allow new users to register an account.", "category": "Registration" },
        "registration_mode": { "value": APP_SETTINGS.get("registration_mode", "admin_approval"), "type": "string", "description": "Method for new user activation: 'direct' or 'admin_approval'.", "category": "Registration" },
        "access_token_expire_minutes": { "value": APP_SETTINGS.get("access_token_expires_minutes", 43200), "type": "integer", "description": "Duration in minutes a user's login session remains valid.", "category": "Authentication" },
        "password_recovery_mode": { "value": "manual", "type": "string", "description": "Password recovery mode: 'manual', 'automatic' (SMTP), or 'system_mail' (uses server's 'mail' command).", "category": "Authentication" },
        "sso_client_enabled": { "value": False, "type": "boolean", "description": "Enable Single Sign-On (SSO) for users to log in via an external provider.", "category": "SSO Client" },
        "sso_client_provider_url": { "value": "", "type": "string", "description": "The OpenID Connect (OIDC) provider's discovery URL (e.g., https://accounts.google.com/.well-known/openid-configuration).", "category": "SSO Client" },
        "sso_client_id": { "value": "", "type": "string", "description": "The Client ID provided by your SSO provider.", "category": "SSO Client" },
        "sso_client_secret": { "value": "", "type": "string", "description": "The Client Secret provided by your SSO provider.", "category": "SSO Client" },
        "sso_client_display_name": { "value": "Login with SSO", "type": "string", "description": "The text displayed on the SSO login button.", "category": "SSO Client" },
        "sso_client_icon_url": { "value": "", "type": "string", "description": "URL for an icon to display on the SSO login button.", "category": "SSO Client" },
        "sso_client_auto_create_users": { "value": True, "type": "boolean", "description": "Automatically create a lollms account for new users who sign in via SSO.", "category": "SSO Client" },
        "scim_enabled": { "value": False, "type": "boolean", "description": "Enable SCIM 2.0 provisioning for users and groups.", "category": "SCIM Provisioning" },
        "scim_token": { "value": "", "type": "string", "description": "The bearer token for authenticating SCIM requests. A new one will be generated if left empty.", "category": "SCIM Provisioning" },
        "smtp_host": { "value": "", "type": "string", "description": "SMTP server address for sending password recovery emails.", "category": "Email Settings" },
        "smtp_port": { "value": 587, "type": "integer", "description": "SMTP server port.", "category": "Email Settings" },
        "smtp_user": { "value": "", "type": "string", "description": "Username for SMTP authentication.", "category": "Email Settings" },
        "smtp_password": { "value": "", "type": "string", "description": "Password for SMTP authentication. (Stored in plaintext, use with caution)", "category": "Email Settings" },
        "smtp_from_email": { "value": "", "type": "string", "description": "The 'From' email address for password recovery emails.", "category": "Email Settings" },
        "smtp_use_tls": { "value": True, "type": "boolean", "description": "Use TLS for the SMTP connection.", "category": "Email Settings" },
        "default_lollms_model_name": { "value": "", "type": "string", "description": "Default model name assigned to newly created users.", "category": "Defaults" },
        "default_llm_ctx_size": { "value": 32000, "type": "integer", "description": "Default context size (in tokens) for new users.", "category": "Defaults" },
        "default_llm_temperature": { "value": 0.7, "type": "float", "description": "Default generation temperature for new users.", "category": "Defaults" },
        "default_user_ui_level": { "value": 0, "type": "integer", "description": "Default UI level for new users (0: Beginner, 2: Intermediate, 4: Expert).", "category": "Defaults" },
        "default_auto_title": { "value": False, "type": "boolean", "description": "Enable automatic discussion title generation for new users by default.", "category": "Defaults" },
        "default_safe_store_vectorizer": { "value": "default_st", "type": "string", "description": "Default vectorizer alias or name for newly created datastores.", "category": "RAG" },
        "restrict_vectorizers_to_aliases": { "value": False, "type": "boolean", "description": "If enabled, users can only choose from the admin-defined RAG Bindings when creating a new Data Store.", "category": "RAG" },
        "default_chunk_size": { "value": 1024, "type": "integer", "description": "The default number of characters per text chunk for RAG indexing.", "category": "RAG" },
        "default_chunk_overlap": { "value": 256, "type": "integer", "description": "The default number of overlapping characters between adjacent text chunks.", "category": "RAG" },
        "allow_user_chunking_config": { "value": True, "type": "boolean", "description": "If enabled, users can specify their own chunk size and overlap when creating a Data Store.", "category": "RAG" },
        "force_model_mode": { "value": "disabled", "type": "string", "description": "Global model override mode: 'disabled', 'force_once' (sets user pref), 'force_always' (overrides session).", "category": "Global LLM Overrides" },
        "force_model_name": { "value": "", "type": "string", "description": "The model name to force on all users. (e.g., 'ollama/llama3').", "category": "Global LLM Overrides" },
        "force_tti_model_mode": { "value": "disabled", "type": "string", "description": "Global TTI model override mode: 'disabled', 'force_once' (sets user pref), 'force_always' (overrides session).", "category": "Global TTI Overrides" },
        "force_tti_model_name": { "value": "", "type": "string", "description": "The TTI model name to force on all users. (e.g., 'diffusers/stable-diffusion-v1-5').", "category": "Global TTI Overrides" },
        "force_iti_model_mode": { "value": "disabled", "type": "string", "description": "Global Image Editing model override mode: 'disabled', 'force_once' (sets user pref), 'force_always' (overrides session).", "category": "Global ITI Overrides" },
        "force_iti_model_name": { "value": "", "type": "string", "description": "The Image Editing model name to force on all users. (e.g., 'diffusers/instruct-pix2pix').", "category": "Global ITI Overrides" },
        "force_context_size": { "value": 4096, "type": "integer", "description": "The context size (in tokens) to force on all users.", "category": "Global LLM Overrides" },
        "openai_api_service_enabled": { "value": False, "type": "boolean", "description": "Enable the OpenAI-compatible v1 API endpoint for users.", "category": "Services" },
        "openai_api_require_key": { "value": True, "type": "boolean", "description": "Require an API key for the OpenAI-compatible v1 API endpoint. If disabled, requests without a key will be handled by the primary admin account.", "category": "Services" },
        "ollama_service_enabled": { "value": False, "type": "boolean", "description": "Enable the Ollama service endpoint for users (OpenAI compatible).", "category": "Services" },
        "ollama_require_key": { "value": True, "type": "boolean", "description": "Require an API key for the Ollama service endpoint. If disabled, requests without a key will be handled by the primary admin account.", "category": "Services" },
        "model_display_mode": { "value": "mixed", "type": "string", "description": "How models are displayed to users: 'original' (shows raw names), 'aliased' (shows only models with aliases), 'mixed' (shows aliases where available, originals otherwise).", "category": "Models" },
        "tti_model_display_mode": { "value": "mixed", "type": "string", "description": "How TTI models are displayed to users: 'original' (shows raw names), 'aliased' (shows only models with aliases), 'mixed' (shows aliases where available, originals otherwise).", "category": "Models" },
        "tts_model_display_mode": { "value": "mixed", "type": "string", "description": "How TTS models are displayed to users: 'original' (shows raw names), 'aliased' (shows only models with aliases), 'mixed' (shows aliases where available, originals otherwise).", "category": "Models" },
        "stt_model_display_mode": { "value": "mixed", "type": "string", "description": "How STT models are displayed to users: 'original' (shows raw names), 'aliased' (shows only models with aliases), 'mixed' (shows aliases where available, originals otherwise).", "category": "Models" },
        "rag_model_display_mode": { "value": "mixed", "type": "string", "description": "How RAG models are displayed to users: 'original' (shows raw names), 'aliased' (shows only models with aliases), 'mixed' (shows aliases where available, originals otherwise).", "category": "Models" },
        "lock_all_context_sizes": { "value": False, "type": "boolean", "description": "Lock context size for all aliased models, preventing users from changing it.", "category": "Models" },
        "ai_bot_enabled": { "value": False, "type": "boolean", "description": "Enable the @lollms AI bot to respond to mentions in the social feed.", "category": "AI Bot" },
        "ai_bot_system_prompt": { "value": "You are lollms, a helpful AI assistant integrated into this social platform. When a user mentions you using '@lollms', you should respond to their post helpfully and concisely. Your goal is to be a friendly and informative presence in the community.", "type": "text", "description": "The system prompt to use for the bot if no personality is selected.", "category": "AI Bot" },
        "ai_bot_binding_model": { "value": "", "type": "string", "description": "The model used by the AI Bot.", "category": "AI Bot" },
        "ai_bot_personality_id": { "value": "", "type": "string", "description": "The personality used by the AI Bot (optional).", "category": "AI Bot" },
        "ai_bot_moderation_enabled": { "value": False, "type": "boolean", "description": "Enable moderation for AI Bot.", "category": "AI Bot" },
        "ai_bot_moderation_criteria": { "value": "Be polite and respectful. No hate speech, spam, or explicit content.", "type": "text", "description": "Criteria for AI Bot moderation.", "category": "AI Bot" },
        "welcome_text": { "value": "lollms", "type": "string", "description": "The main text displayed on the welcome page.", "category": "Welcome Page" },
        "welcome_slogan": { "value": "One tool to rule them all", "type": "string", "description": "The slogan displayed under the main text on the welcome page.", "category": "Welcome Page" },
        "welcome_logo_url": { "value": "", "type": "string", "description": "URL to a custom logo for the welcome page. Leave empty for default.", "category": "Welcome Page" },
        "latex_builder_enabled": { "value": False, "type": "boolean", "description": "Enable the LaTeX builder to compile LaTeX code blocks into PDFs.", "category": "Builders" },
        "latex_builder_path": { "value": "pdflatex", "type": "string", "description": "Path to the pdflatex executable. On Windows, this might be 'C:\\texlive\\2023\\bin\\win32\\pdflatex.exe'. On Linux, 'pdflatex' should suffice if it's in the system's PATH.", "category": "Builders" },
        "export_to_txt_enabled": { "value": True, "type": "boolean", "description": "Allow users to export messages as plain text (.txt) files.", "category": "Builders" },
        "export_to_markdown_enabled": { "value": True, "type": "boolean", "description": "Allow users to export messages as Markdown (.md) files.", "category": "Builders" },
        "export_to_html_enabled": { "value": True, "type": "boolean", "description": "Allow users to export messages as HTML (.html) files.", "category": "Builders" },
        "export_to_pdf_enabled": { "value": False, "type": "boolean", "description": "Allow users to export messages as PDF (.pdf) files. Requires PyMuPDF (fitz).", "category": "Builders" },
        "export_to_docx_enabled": { "value": False, "type": "boolean", "description": "Allow users to export messages as Word (.docx) files. Requires python-docx.", "category": "Builders" },
        "export_to_xlsx_enabled": { "value": False, "type": "boolean", "description": "Allow users to export messages as Excel (.xlsx) files. Requires openpyxl.", "category": "Builders" },
        "export_to_pptx_enabled": { "value": False, "type": "boolean", "description": "Allow users to export messages as PowerPoint (.pptx) files. Requires python-pptx.", "category": "Builders" },
        "rss_feed_enabled": { "value": False, "type": "boolean", "description": "Enable the periodic fetching of RSS feeds to generate news and fun facts.", "category": "News Feed" },
        "rss_feed_check_interval_minutes": { "value": 60, "type": "integer", "description": "How often (in minutes) to check for new articles in the RSS feeds.", "category": "News Feed" },
        "rss_generate_fun_facts": { "value": False, "type": "boolean", "description": "When enabled, an AI will generate a 'fun fact' from the content of each new RSS article.", "category": "News Feed" },
        "rss_news_retention_days": { "value": 1, "type": "integer", "description": "How many days to keep news articles. Older articles will be deleted daily. Set to 0 to disable cleanup.", "category": "News Feed" }
    }

    select_keys_query = text("SELECT key FROM global_configs")
    existing_keys = {row[0] for row in connection.execute(select_keys_query).fetchall()}
    
    missing_keys = set(all_possible_settings.keys()) - existing_keys

    if missing_keys:
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
        connection.execute(insert_stmt, configs_to_insert)
        connection.commit()

def _bootstrap_fun_facts(connection):
    """
    Reads fun facts from the JSON file and populates the database if the tables are empty.
    """
    print("INFO: Checking and bootstrapping fun facts in the database.")
    
    try:
        category_count = connection.execute(text("SELECT COUNT(id) FROM fun_fact_categories")).scalar_one()
        if category_count > 0:
            return

        fun_facts_path = Path(__file__).parent.parent / "assets" / "fun_facts.json"
        if not fun_facts_path.exists():
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
            
            result = connection.execute(category_insert_stmt.values(name=category_name, is_active=True, color=color))
            category_id = result.inserted_primary_key[0] 
            
            facts_to_insert = [
                {"content": fact_content, "category_id": category_id}
                for fact_content in facts if fact_content.strip()
            ]
            
            if facts_to_insert:
                connection.execute(fact_insert_stmt, facts_to_insert)
        
        connection.commit()

    except Exception as e:
        print(f"CRITICAL: Failed to bootstrap fun facts. Error: {e}")
        trace_exception(e)
        connection.rollback()

def _bootstrap_lollms_user(connection):
    """
    Ensures the special @lollms user exists in the database.
    """
    from backend.security import get_password_hash
    import secrets

    lollms_user_exists = connection.execute(text("SELECT 1 FROM users WHERE username = 'lollms'")).first()
    if not lollms_user_exists:
        print("INFO: Creating special AI user '@lollms'.")
        dummy_password = secrets.token_hex(32)
        hashed_password = get_password_hash(dummy_password[:72])
        
        # THIS WAS THE SOURCE OF THE INTEGRITY ERROR: Added force_ai_response_language
        connection.execute(
            text("""
                INSERT INTO users (
                    username, hashed_password, is_admin, is_active, is_searchable, 
                    first_login_done, receive_notification_emails, is_moderator,
                    put_thoughts_in_context, auto_title, chat_active, first_page,
                    show_token_counter, rag_use_graph, tell_llm_os, share_dynamic_info_with_llm,
                    include_memory_date_in_context, message_font_size,
                    image_generation_enabled, image_annotation_enabled,
                    force_ai_response_language, share_personal_info_with_llm, note_generation_enabled
                )
                VALUES (
                    :username, :hashed_password, :is_admin, :is_active, :is_searchable, 
                    :first_login_done, :receive_notification_emails, :is_moderator,
                    :put_thoughts_in_context, :auto_title, :chat_active, :first_page,
                    :show_token_counter, :rag_use_graph, :tell_llm_os, :share_dynamic_info_with_llm,
                    :include_memory_date_in_context, :message_font_size,
                    :image_generation_enabled, :image_annotation_enabled,
                    :force_ai_response_language, :share_personal_info_with_llm, :note_generation_enabled
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
                "rag_use_graph": False,
                "tell_llm_os": False,
                "share_dynamic_info_with_llm": True,
                "include_memory_date_in_context": False,
                "message_font_size": 14,
                "image_generation_enabled": False,
                "image_annotation_enabled": False,
                "force_ai_response_language": False, # Added missing required field
                "share_personal_info_with_llm": False,
                "note_generation_enabled": False
            }
        )
        connection.commit()
        print("INFO: AI user '@lollms' created successfully.")
    else:
        print("INFO: AI user '@lollms' already exists.")

def run_schema_migrations_and_bootstrap(connection, inspector):
    _migrate_user_data_folders(connection)

    if inspector.has_table("global_configs"):
        _bootstrap_global_settings(connection)

        keys_to_remove_str = "('default_mcps', 'default_personalities')"
        try:
            result = connection.execute(text(f"DELETE FROM global_configs WHERE key IN {keys_to_remove_str}"))
            if result.rowcount > 0:
                connection.commit()
        except Exception as e:
            print(f"WARNING: Could not remove deprecated global settings. Error: {e}")
            connection.rollback()

    if inspector.has_table("tasks"):
        task_columns_db = [col['name'] for col in inspector.get_columns('tasks')]
        if 'updated_at' not in task_columns_db:
            try:
                connection.execute(text("ALTER TABLE tasks ADD COLUMN updated_at DATETIME"))
                connection.execute(text("UPDATE tasks SET updated_at = created_at WHERE updated_at IS NULL"))
                connection.commit()
            except Exception as e:
                connection.rollback()
                
    if inspector.has_table("saved_prompts"):
        columns_db = [col['name'] for col in inspector.get_columns('saved_prompts')]
        new_cols_defs = { "category": "VARCHAR", "author": "VARCHAR", "description": "TEXT", "icon": "TEXT", "version": "VARCHAR", "repository": "VARCHAR", "folder_name": "VARCHAR" }
        for col_name, col_sql_def in new_cols_defs.items():
            if col_name not in columns_db:
                connection.execute(text(f"ALTER TABLE saved_prompts ADD COLUMN {col_name} {col_sql_def}"))
        connection.commit()

        full_columns_info = inspector.get_columns('saved_prompts')
        owner_user_id_col_info_full = next((col for col in full_columns_info if col['name'] == 'owner_user_id'), None)
        if owner_user_id_col_info_full and owner_user_id_col_info_full.get('nullable') == False:
            try:
                data = connection.execute(text("SELECT * FROM saved_prompts")).mappings().all()
                connection.execute(text("DROP TABLE saved_prompts;"))
                SavedPrompt.__table__.create(connection)
                if data:
                    new_cols_names = [c.name for c in SavedPrompt.__table__.columns]
                    for row in data:
                        row_data = {k: v for k, v in row.items() if k in new_cols_names}
                        connection.execute(SavedPrompt.__table__.insert().values(row_data))
                connection.commit()
            except Exception as e:
                connection.rollback()
                raise e
            
    if inspector.has_table("direct_messages"):
        direct_messages_columns_db = [col['name'] for col in inspector.get_columns('direct_messages')]
        new_direct_messages_cols_defs = { "image_references": "JSON" }
        for col_name, col_sql_def in new_direct_messages_cols_defs.items():
            if col_name not in direct_messages_columns_db:
                connection.execute(text(f"ALTER TABLE direct_messages ADD COLUMN {col_name} {col_sql_def}"))
        connection.commit()
        
        dm_cols_full = inspector.get_columns('direct_messages')
        receiver_col_info = next((c for c in dm_cols_full if c['name'] == 'receiver_id'), None)
        if receiver_col_info and not receiver_col_info.get('nullable'):
            try:
                data = connection.execute(text("SELECT * FROM direct_messages")).mappings().all()
                connection.execute(text("DROP TABLE direct_messages;"))
                DirectMessage.__table__.create(connection)
                if data:
                    new_cols = [c.name for c in DirectMessage.__table__.columns]
                    insert_stmt = DirectMessage.__table__.insert()
                    for row in data:
                        row_data = {k: v for k, v in row.items() if k in new_cols}
                        for date_field in ['sent_at', 'read_at']:
                            if date_field in row_data and isinstance(row_data[date_field], str):
                                try: row_data[date_field] = datetime.fromisoformat(row_data[date_field])
                                except: pass
                        connection.execute(insert_stmt.values(row_data))
                connection.commit()
            except Exception as e:
                connection.rollback()
    
    if inspector.has_table("conversation_members"):
        cm_cols = [c['name'] for c in inspector.get_columns('conversation_members')]
        if 'id' not in cm_cols:
            try:
                data = connection.execute(text("SELECT * FROM conversation_members")).mappings().all()
                connection.execute(text("DROP TABLE conversation_members;"))
                ConversationMember.__table__.create(connection)
                if data:
                    insert_stmt = ConversationMember.__table__.insert()
                    for row in data:
                        row_data = {k: v for k, v in row.items() if k in cm_cols} 
                        connection.execute(insert_stmt.values(row_data))
                connection.commit()
            except Exception as e:
                connection.rollback()

    if inspector.has_table("database_version"):
        db_version_cols = inspector.get_columns('database_version')
        version_col_info = next((col for col in db_version_cols if col['name'] == 'version'), None)
        if version_col_info and "VARCHAR" not in str(version_col_info['type']).upper() and "TEXT" not in str(version_col_info['type']).upper():
            try:
                old_version_data = connection.execute(text("SELECT id, version FROM database_version")).mappings().first()
                connection.execute(text("DROP TABLE database_version;"))
                DatabaseVersion.__table__.create(connection)
                if old_version_data:
                    version_val = str(old_version_data['version']) if isinstance(old_version_data['version'], (int, float)) else old_version_data['version']
                    connection.execute(DatabaseVersion.__table__.insert().values(id=old_version_data['id'], version=version_val))
                connection.commit()
            except Exception as e:
                connection.rollback()
                raise

    if inspector.has_table("llm_bindings"):
        llm_bindings_columns_db = [col['name'] for col in inspector.get_columns('llm_bindings')]
        columns_requiring_rebuild = ['verify_ssl_certificate', 'host_address', 'service_key', 'models_path', 'ctx_size', 'user_name', 'ai_name', 'temperature', 'top_k', 'top_p', 'repeat_penalty', 'repeat_last_n']
        needs_rebuild = any(col_name in llm_bindings_columns_db for col_name in columns_requiring_rebuild)

        if needs_rebuild:
            try:
                data_proxy = connection.execute(text("SELECT * FROM llm_bindings"))
                column_names = data_proxy.keys()
                rows = data_proxy.fetchall()
                data_to_migrate = [dict(zip(column_names, row)) for row in rows]
                connection.execute(text("PRAGMA foreign_keys=off;"))
                new_rows_data = []              
                if data_to_migrate:
                    for row in data_to_migrate:
                        existing_config = row.get('config')
                        if isinstance(existing_config, str):
                            try: existing_config = json.loads(existing_config)
                            except (json.JSONDecodeError, TypeError): existing_config = {}
                        elif not isinstance(existing_config, dict): existing_config = {}
                        
                        json_to_add = {}
                        if 'verify_ssl_certificate' in row and row['verify_ssl_certificate'] is not None: json_to_add['verify_ssl_certificate'] = bool(row['verify_ssl_certificate'])
                        if 'host_address' in row and row['host_address'] is not None: json_to_add['host_address'] = row['host_address']
                        # ... (add other fields as needed) ...

                        created_at_dt = None
                        if 'created_at' in row and row['created_at'] is not None:
                            if isinstance(row['created_at'], str):
                                try: created_at_dt = datetime.fromisoformat(row['created_at'])
                                except ValueError: pass
                            else: created_at_dt = row['created_at']

                        updated_at_dt = None
                        if 'updated_at' in row and row['updated_at'] is not None:
                            if isinstance(row['updated_at'], str):
                                try: updated_at_dt = datetime.fromisoformat(row['updated_at'])
                                except ValueError: pass
                            else: updated_at_dt = row['updated_at']

                        new_row_data = {
                            'id': row['id'],
                            'alias': row.get('alias') or row.get('name') or f"binding_{row['id']}",
                            'name': row.get('name') or row.get('alias') or f"binding_{row['id']}",
                            'config': {**existing_config, **json_to_add},
                            'default_model_name': row.get('default_model_name'),
                            'is_active': row.get('is_active', True),
                            'created_at': created_at_dt,
                            'updated_at': updated_at_dt,
                            'model_aliases': row.get('model_aliases')
                        }
                        if new_row_data['alias'] is None or new_row_data['name'] is None: continue
                        new_rows_data.append(new_row_data)

                connection.execute(text("DROP TABLE llm_bindings;"))
                connection.commit()
                LLMBinding.__table__.create(connection)
                for new_row_data in new_rows_data:
                    connection.execute(LLMBinding.__table__.insert().values(new_row_data))
                connection.commit()
            except Exception as e:
                connection.rollback()
                raise e
            finally:
                connection.execute(text("PRAGMA foreign_keys=on;"))

    if inspector.has_table("personalities"):
        personality_columns_db = [col['name'] for col in inspector.get_columns('personalities')]
        new_personality_cols_defs = { "active_mcps": "JSON", "data_source_type": "VARCHAR DEFAULT 'none' NOT NULL", "data_source": "TEXT", "version": "VARCHAR", "repository": "VARCHAR", "folder_name": "VARCHAR" }
        for col_name, col_sql_def in new_personality_cols_defs.items():
            if col_name not in personality_columns_db:
                connection.execute(text(f"ALTER TABLE personalities ADD COLUMN {col_name} {col_sql_def}"))
        connection.commit()

    if not inspector.has_table("user_voices"):
        from backend.db.models.voice import UserVoice
        UserVoice.__table__.create(connection)
        connection.commit()
    else:
        voice_columns_db = [col['name'] for col in inspector.get_columns('user_voices')]
        new_voice_cols_defs = { "speed": "FLOAT DEFAULT 1.0 NOT NULL", "gain": "FLOAT DEFAULT 0.0 NOT NULL", "reverb_params": "JSON" }
        for col_name, col_sql_def in new_voice_cols_defs.items():
            if col_name not in voice_columns_db:
                connection.execute(text(f"ALTER TABLE user_voices ADD COLUMN {col_name} {col_sql_def}"))
        connection.commit()

    if not inspector.has_table("user_images"):
        from backend.db.models.image import UserImage
        UserImage.__table__.create(connection)
        connection.commit()
    else:
        image_columns_db = [col['name'] for col in inspector.get_columns('user_images')]
        if 'width' not in image_columns_db: connection.execute(text("ALTER TABLE user_images ADD COLUMN width INTEGER"))
        if 'height' not in image_columns_db: connection.execute(text("ALTER TABLE user_images ADD COLUMN height INTEGER"))
        if 'negative_prompt' not in image_columns_db: connection.execute(text("ALTER TABLE user_images ADD COLUMN negative_prompt TEXT"))
        if 'seed' not in image_columns_db: connection.execute(text("ALTER TABLE user_images ADD COLUMN seed INTEGER"))
        if 'generation_params' not in image_columns_db: connection.execute(text("ALTER TABLE user_images ADD COLUMN generation_params JSON"))
        connection.commit()

    if inspector.has_table("users"):
        user_columns_db = [col['name'] for col in inspector.get_columns('users')]

        if 'external_id' not in user_columns_db:
            try:
                connection.execute(text("ALTER TABLE users ADD COLUMN external_id VARCHAR"))
                connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_external_id ON users (external_id)"))
                connection.commit()
            except Exception: connection.rollback()
        
        if 'scratchpad' in user_columns_db and 'data_zone' not in user_columns_db:
            try:
                connection.execute(text("ALTER TABLE users RENAME COLUMN scratchpad TO data_zone"))
                user_columns_db = [col['name'] for col in inspector.get_columns('users')]
                connection.commit()
            except Exception: connection.rollback()
        
        # --- Migration for new fields ---
        if 'note_generation_enabled' not in user_columns_db:
            try:
                connection.execute(text("ALTER TABLE users ADD COLUMN note_generation_enabled BOOLEAN DEFAULT 0 NOT NULL"))
                connection.commit()
            except Exception: connection.rollback()

        if 'preferred_name' not in user_columns_db:
            try:
                connection.execute(text("ALTER TABLE users ADD COLUMN preferred_name VARCHAR"))
                connection.commit()
            except Exception: connection.rollback()

        if 'user_personal_info' not in user_columns_db:
            try:
                connection.execute(text("ALTER TABLE users ADD COLUMN user_personal_info TEXT"))
                connection.commit()
            except Exception: connection.rollback()

        if 'share_personal_info_with_llm' not in user_columns_db:
            try:
                connection.execute(text("ALTER TABLE users ADD COLUMN share_personal_info_with_llm BOOLEAN DEFAULT 0 NOT NULL"))
                connection.commit()
            except Exception: connection.rollback()
        
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
            "force_ai_response_language": "BOOLEAN DEFAULT 0 NOT NULL",
            "fun_mode": "BOOLEAN DEFAULT 0 NOT NULL",
            "chat_active": "BOOLEAN DEFAULT 1 NOT NULL",
            "first_page": "VARCHAR DEFAULT 'feed' NOT NULL",
            "receive_notification_emails": "BOOLEAN DEFAULT 1 NOT NULL",
            "show_token_counter": "BOOLEAN DEFAULT 1 NOT NULL",
            "is_searchable": "BOOLEAN DEFAULT 1 NOT NULL",
            "first_login_done": "BOOLEAN DEFAULT 0 NOT NULL",
            "data_zone": "TEXT", "memory": "TEXT",
            "is_moderator": "BOOLEAN DEFAULT 0 NOT NULL",
            "tti_binding_model_name": "VARCHAR",
            "iti_binding_model_name": "VARCHAR",
            "tti_models_config": "JSON",
            "tts_binding_model_name": "VARCHAR",
            "tts_models_config": "JSON",
            "stt_binding_model_name": "VARCHAR",
            "stt_models_config": "JSON",
            "active_voice_id": "VARCHAR REFERENCES user_voices(id) ON DELETE SET NULL",
            "include_memory_date_in_context": "BOOLEAN DEFAULT 0 NOT NULL",
            "coding_style_constraints": "TEXT",
            "programming_language_preferences": "TEXT",
            "tell_llm_os": "BOOLEAN DEFAULT 0 NOT NULL",
            "share_dynamic_info_with_llm": "BOOLEAN DEFAULT 1 NOT NULL",
            "message_font_size": "INTEGER DEFAULT 14 NOT NULL",
            "last_discussion_id": "VARCHAR",
            "image_studio_prompt": "TEXT",
            "image_studio_negative_prompt": "TEXT",
            "image_studio_image_size": "VARCHAR DEFAULT '1024x1024'",
            "image_studio_n_images": "INTEGER DEFAULT 1",
            "image_studio_seed": "INTEGER DEFAULT -1",
            "image_studio_generation_params": "JSON",
            "image_generation_enabled": "BOOLEAN DEFAULT 0 NOT NULL",
            "image_generation_system_prompt": "TEXT",
            "image_annotation_enabled": "BOOLEAN DEFAULT 0 NOT NULL",
            "reasoning_activation": "BOOLEAN DEFAULT 0",
            "reasoning_effort": "VARCHAR",
            "reasoning_summary": "BOOLEAN DEFAULT 0"
        }
        
        added_cols = []
        for col_name, col_sql_def in new_user_cols_defs.items():
            if col_name not in user_columns_db:
                try:
                    connection.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_sql_def}"))
                    added_cols.append(col_name)
                    connection.commit()
                except Exception: connection.rollback()
        
        if 'chat_active' in added_cols:
             connection.execute(text("UPDATE users SET chat_active = 1 WHERE chat_active IS NULL"))
             connection.commit()
        elif 'chat_active' in user_columns_db:
             connection.execute(text("UPDATE users SET chat_active = 1 WHERE chat_active = 0"))
             connection.commit()

        if 'is_active' in added_cols:
            connection.execute(text("UPDATE users SET is_active = 1 WHERE is_active IS NULL"))
            connection.commit()
        
        if 'is_admin' in added_cols:
            connection.execute(text("UPDATE users SET is_admin = 0 WHERE is_admin IS NULL"))
            connection.commit()
        if 'is_moderator' in added_cols:
            connection.execute(text("UPDATE users SET is_moderator = 0 WHERE is_moderator IS NULL"))
            connection.commit()

        if 'put_thoughts_in_context' not in user_columns_db:
            try:
                connection.execute(text("UPDATE users SET put_thoughts_in_context = 0 WHERE put_thoughts_in_context IS NULL"))
                connection.commit()
            except Exception: connection.rollback()

        if 'first_login_done' in added_cols:
            try:
                connection.execute(text("UPDATE users SET first_login_done = 1 WHERE first_login_done IS NULL"))
                connection.commit()
            except Exception: connection.rollback()

        user_constraints = inspector.get_unique_constraints('users')
        if 'email' in new_user_cols_defs and not any(c['name'] == 'uq_user_email' for c in user_constraints):
            try:
                connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_user_email ON users (email) WHERE email IS NOT NULL"))
                connection.commit()
            except Exception: connection.rollback()
        
        if 'password_reset_token' in new_user_cols_defs and not any(c['name'] == 'uq_password_reset_token' for c in user_constraints):
            try:
                connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_password_reset_token ON users (password_reset_token) WHERE password_reset_token IS NOT NULL"))
                connection.commit()
            except Exception: connection.rollback()
        
    if inspector.has_table("posts"):
        posts_columns_db = [col['name'] for col in inspector.get_columns('posts')]
        if 'group_id' not in posts_columns_db:
            try:
                connection.execute(text("ALTER TABLE posts ADD COLUMN group_id INTEGER REFERENCES user_groups(id) ON DELETE CASCADE"))
                connection.commit()
            except Exception: connection.rollback()
        
        if 'moderation_status' not in posts_columns_db:
            try:
                connection.execute(text("ALTER TABLE posts ADD COLUMN moderation_status VARCHAR DEFAULT 'pending' NOT NULL"))
                connection.execute(text("UPDATE posts SET moderation_status = 'pending'"))
                connection.commit()
            except Exception: connection.rollback()

        try:
            result = connection.execute(text("UPDATE posts SET visibility = LOWER(visibility) WHERE visibility != LOWER(visibility)"))
            if result.rowcount > 0: connection.commit()
        except Exception: connection.rollback()

    if inspector.has_table("comments"):
        comments_columns_db = [col['name'] for col in inspector.get_columns('comments')]
        if 'moderation_status' not in comments_columns_db:
            try:
                connection.execute(text("ALTER TABLE comments ADD COLUMN moderation_status VARCHAR DEFAULT 'pending' NOT NULL"))
                connection.execute(text("UPDATE comments SET moderation_status = 'pending'"))
                connection.commit()
            except Exception: connection.rollback()

    if inspector.has_table("discussion_groups"):
        discussion_groups_columns = [col['name'] for col in inspector.get_columns('discussion_groups')]
        if 'parent_id' not in discussion_groups_columns:
            try:
                connection.execute(text("ALTER TABLE discussion_groups ADD COLUMN parent_id VARCHAR REFERENCES discussion_groups(id) ON DELETE SET NULL"))
                connection.commit()
            except Exception: connection.rollback()

    if not inspector.has_table("user_memories"):
        UserMemory.__table__.create(connection)
        connection.commit()
    else:
        user_memories_columns = [col['name'] for col in inspector.get_columns('user_memories')]
        if 'owner_user_id' not in user_memories_columns:
            try:
                connection.execute(text("ALTER TABLE user_memories ADD COLUMN owner_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE"))
                admin_user = connection.execute(text("SELECT id FROM users WHERE is_admin = 1 ORDER BY id ASC LIMIT 1")).first()
                if admin_user:
                    connection.execute(text(f"UPDATE user_memories SET owner_user_id = {admin_user} WHERE owner_user_id IS NULL"))
                connection.commit()
            except Exception: connection.rollback()
        
        if 'updated_at' not in user_memories_columns:
            try:
                connection.execute(text("ALTER TABLE user_memories ADD COLUMN updated_at DATETIME"))
                connection.execute(text("UPDATE user_memories SET updated_at = created_at WHERE updated_at IS NULL"))
                connection.commit()
            except Exception: connection.rollback()

        try:
            result = connection.execute(text("DELETE FROM user_memories WHERE title IS NULL OR title = '' OR content IS NULL OR content = ''"))
            if result.rowcount > 0: connection.commit()
        except Exception: connection.rollback()
            
    if not inspector.has_table("user_groups"):
        if inspector.has_table("scim_groups"):
            connection.execute(text("ALTER TABLE scim_groups RENAME TO user_groups"))
        else:
            Group.__table__.create(connection)
        
        group_columns = [col['name'] for col in inspector.get_columns('user_groups')]
        new_group_cols = { "description": "TEXT", "icon": "TEXT", "owner_id": "INTEGER REFERENCES users(id) ON DELETE SET NULL" }
        for col_name, col_type in new_group_cols.items():
            if col_name not in group_columns:
                connection.execute(text(f"ALTER TABLE user_groups ADD COLUMN {col_name} {col_type}"))
        connection.commit()

    if not inspector.has_table("user_group_link"):
        from backend.db.base import user_group_link as user_group_link_table
        user_group_link_table.create(connection)
        connection.commit()

    _bootstrap_lollms_user(connection)

    if inspector.has_table("mcps"):
        mcp_columns_db = [col['name'] for col in inspector.get_columns('mcps')]
        new_mcp_cols_defs = { "active": "BOOLEAN DEFAULT 1 NOT NULL", "type": "VARCHAR", "icon": "TEXT", "authentication_type": "VARCHAR", "authentication_key": "VARCHAR", "sso_redirect_uri": "VARCHAR", "sso_user_infos_to_share": "JSON", "client_id": "VARCHAR" }
        for col_name, col_sql_def in new_mcp_cols_defs.items():
            if col_name not in mcp_columns_db:
                connection.execute(text(f"ALTER TABLE mcps ADD COLUMN {col_name} {col_sql_def}"))
        connection.commit()
        
        if 'client_id' in new_mcp_cols_defs:
            mcps_to_update = connection.execute(text("SELECT id, name FROM mcps WHERE client_id IS NULL")).fetchall()
            if mcps_to_update:
                app_columns_db = []
                if inspector.has_table('apps'): app_columns_db = [col['name'] for col in inspector.get_columns('apps')]
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
                connection.commit()

        mcp_constraints = inspector.get_unique_constraints('mcps')
        if 'client_id' in new_mcp_cols_defs and not any(c['name'] == 'uq_mcp_client_id' for c in mcp_constraints):
            try:
                connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_mcp_client_id ON mcps (client_id) WHERE client_id IS NOT NULL"))
                connection.commit()
            except Exception: connection.rollback()

    if inspector.has_table("apps"):
        app_columns_db = [col['name'] for col in inspector.get_columns('apps')]
        url_col_info = next((col for col in inspector.get_columns('apps') if col['name'] == 'url'), None)

        if url_col_info and url_col_info.get('nullable') == 0:
            try:
                data = connection.execute(text("SELECT * FROM apps")).mappings().all()
                connection.execute(text("DROP TABLE apps;"))
                App.__table__.create(connection)
                if data:
                    new_cols_names = [c.name for c in App.__table__.columns]
                    used_ports_during_migration_batch = set()
                    for row in data:
                        row_data = {k: v for k, v in row.items() if k in new_cols_names}
                        if 'created_at' in row_data and isinstance(row_data['created_at'], str):
                            try: row_data['created_at'] = datetime.fromisoformat(row_data['created_at'])
                            except ValueError: row_data['created_at'] = None
                        if 'updated_at' in row_data and isinstance(row_data['updated_at'], str):
                            try: row_data['updated_at'] = datetime.fromisoformat(row_data['updated_at'])
                            except ValueError: row_data['updated_at'] = None
                        if 'port' in row_data and row_data['port'] is not None:
                            original_port = row_data['port']
                            new_port = _find_unique_port_for_migration(connection, original_port, used_ports_during_migration_batch)
                            row_data['port'] = new_port
                            used_ports_during_migration_batch.add(new_port)
                        if 'client_id' not in row_data or row_data['client_id'] is None:
                            base_slug = re.sub(r'[^a-z0-9_]+', '', (row_data.get('name', 'app')).lower().replace(' ', '_'))
                            new_client_id = base_slug
                            counter = 1
                            while True:
                                app_conflict = connection.execute(text("SELECT 1 FROM apps WHERE client_id = :cid"), {"cid": new_client_id}).first()
                                mcp_conflict = connection.execute(text("SELECT 1 FROM mcps WHERE client_id = :cid"), {"cid": new_client_id}).first()
                                if not app_conflict and not mcp_conflict: break
                                new_client_id = f"{base_slug}_{counter}"
                                counter += 1
                            row_data['client_id'] = new_client_id
                        connection.execute(App.__table__.insert().values(row_data))
                connection.commit()
            except Exception as e:
                connection.rollback()
                raise e

        new_app_cols_defs = { "icon": "TEXT", "active": "BOOLEAN DEFAULT 1 NOT NULL", "type": "VARCHAR", "authentication_type": "VARCHAR", "authentication_key": "VARCHAR", "sso_redirect_uri": "VARCHAR", "sso_user_infos_to_share": "JSON", "client_id": "VARCHAR", "description": "TEXT", "author": "VARCHAR", "version": "VARCHAR", "category": "VARCHAR", "tags": "JSON", "is_installed": "BOOLEAN DEFAULT 0 NOT NULL", "status": "VARCHAR DEFAULT 'stopped' NOT NULL", "autostart": "BOOLEAN DEFAULT 0 NOT NULL", "port": "INTEGER", "pid": "INTEGER", "app_metadata": "JSON", "folder_name": "VARCHAR", "allow_openai_api_access": "BOOLEAN DEFAULT 0 NOT NULL" }
        app_columns_db_after_rebuild = [col['name'] for col in inspector.get_columns('apps')]
        for col_name, col_sql_def in new_app_cols_defs.items():
            if col_name not in app_columns_db_after_rebuild:
                connection.execute(text(f"ALTER TABLE apps ADD COLUMN {col_name} {col_sql_def}"))
        connection.commit()

        if 'client_id' in new_app_cols_defs:
            apps_to_update = connection.execute(text("SELECT id, name FROM apps WHERE client_id IS NULL")).fetchall()
            if apps_to_update:
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
                connection.commit()
        
        app_constraints = inspector.get_unique_constraints('apps')
        if 'port' in new_app_cols_defs and not any(c['name'] == 'uq_app_port' for c in app_constraints):
            try:
                connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_app_port ON apps (port) WHERE port IS NOT NULL"))
                connection.commit()
            except Exception: connection.rollback()
        
        if 'client_id' in new_app_cols_defs and not any(c['name'] == 'uq_app_client_id' for c in app_constraints):
            try:
                connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_app_client_id ON apps (client_id) WHERE client_id IS NOT NULL"))
                connection.commit()
            except Exception: connection.rollback()

    if inspector.has_table("system_apps"):
        system_app_columns_db = [col['name'] for col in inspector.get_columns('system_apps')]
        new_system_app_cols_defs = { "sso_redirect_uri": "VARCHAR", "sso_user_infos_to_share": "JSON" }
        for col_name, col_sql_def in new_system_app_cols_defs.items():
            if col_name not in system_app_columns_db:
                connection.execute(text(f"ALTER TABLE system_apps ADD COLUMN {col_name} {col_sql_def}"))
        connection.commit()

    if inspector.has_table("app_zoo_repositories"):
        columns_db = [col['name'] for col in inspector.get_columns('app_zoo_repositories')]
        if 'is_deletable' not in columns_db: connection.execute(text("ALTER TABLE app_zoo_repositories ADD COLUMN is_deletable BOOLEAN DEFAULT 1 NOT NULL"))
        if 'type' not in columns_db: connection.execute(text("ALTER TABLE app_zoo_repositories ADD COLUMN type VARCHAR DEFAULT 'git' NOT NULL"))
        connection.commit()

    if inspector.has_table("mcp_zoo_repositories"):
        columns_db = [col['name'] for col in inspector.get_columns('mcp_zoo_repositories')]
        if 'is_deletable' not in columns_db: connection.execute(text("ALTER TABLE mcp_zoo_repositories ADD COLUMN is_deletable BOOLEAN DEFAULT 1 NOT NULL"))
        if 'type' not in columns_db: connection.execute(text("ALTER TABLE mcp_zoo_repositories ADD COLUMN type VARCHAR DEFAULT 'git' NOT NULL"))
        connection.commit()

    if inspector.has_table("prompt_zoo_repositories"):
        columns_db = [col['name'] for col in inspector.get_columns('prompt_zoo_repositories')]
        if 'is_deletable' not in columns_db: connection.execute(text("ALTER TABLE prompt_zoo_repositories ADD COLUMN is_deletable BOOLEAN DEFAULT 1 NOT NULL"))
        if 'type' not in columns_db: connection.execute(text(f"ALTER TABLE prompt_zoo_repositories ADD COLUMN type VARCHAR DEFAULT 'git' NOT NULL"))
        connection.commit()
    
    if not inspector.has_table("personality_zoo_repositories"):
        from backend.db.models.service import PersonalityZooRepository
        PersonalityZooRepository.__table__.create(connection)
        connection.commit()

    if not inspector.has_table("broadcast_messages"):
        from backend.db.models.broadcast import BroadcastMessage
        BroadcastMessage.__table__.create(connection)
        connection.commit()

    if not inspector.has_table("shared_discussion_links"):
        from backend.db.models.discussion import SharedDiscussionLink
        SharedDiscussionLink.__table__.create(connection)
        connection.commit()

    if inspector.has_table("fun_fact_categories"):
        fun_fact_cat_cols = [col['name'] for col in inspector.get_columns('fun_fact_categories')]
        if 'color' not in fun_fact_cat_cols:
            connection.execute(text("ALTER TABLE fun_fact_categories ADD COLUMN color VARCHAR(7) DEFAULT '#4299e1' NOT NULL"))
            connection.commit()

    if not inspector.has_table("fun_fact_categories"):
        FunFactCategory.__table__.create(connection)
    
    if not inspector.has_table("fun_facts"):
        FunFact.__table__.create(connection)

    if not inspector.has_table("rss_feed_sources"):
        from backend.db.models.news import RSSFeedSource
        RSSFeedSource.__table__.create(connection)
        connection.commit()

    if not inspector.has_table("news_articles"):
        from backend.db.models.news import NewsArticle
        NewsArticle.__table__.create(connection)
        connection.commit()

    if not inspector.has_table("tts_bindings"):
        TTSBinding.__table__.create(connection)
        connection.commit()

    if not inspector.has_table("stt_bindings"):
        STTBinding.__table__.create(connection)
        connection.commit()

    if not inspector.has_table("rag_bindings"):
        RAGBinding.__table__.create(connection)
        connection.commit()

    if not inspector.has_table("websocket_connections"):
        WebSocketConnection.__table__.create(connection)
        connection.commit()


    if inspector.has_table("fun_fact_categories"):
        _bootstrap_fun_facts(connection)
    
    if not inspector.has_table("datastores"):
        from backend.db.models.datastore import DataStore, SharedDataStoreLink
        DataStore.__table__.create(connection)
        SharedDataStoreLink.__table__.create(connection)
        connection.commit()
    else:
        datastore_columns_db = [col['name'] for col in inspector.get_columns('datastores')]
        if 'vectorizer_name' not in datastore_columns_db: connection.execute(text("ALTER TABLE datastores ADD COLUMN vectorizer_name VARCHAR"))
        if 'vectorizer_config' not in datastore_columns_db: connection.execute(text("ALTER TABLE datastores ADD COLUMN vectorizer_config JSON"))
        if 'chunk_size' not in datastore_columns_db: connection.execute(text("ALTER TABLE datastores ADD COLUMN chunk_size INTEGER"))
        if 'chunk_overlap' not in datastore_columns_db: connection.execute(text("ALTER TABLE datastores ADD COLUMN chunk_overlap INTEGER"))
        connection.execute(text("UPDATE datastores SET vectorizer_name = 'st' WHERE vectorizer_name IS NULL"))
        connection.execute(text("UPDATE datastores SET vectorizer_config = '{}' WHERE vectorizer_config IS NULL"))
        connection.execute(text(f"UPDATE datastores SET chunk_size = {SAFE_STORE_DEFAULTS.get('default_chunk_size', 1024)} WHERE chunk_size IS NULL"))
        connection.execute(text(f"UPDATE datastores SET chunk_overlap = {SAFE_STORE_DEFAULTS.get('default_chunk_overlap', 256)} WHERE chunk_overlap IS NULL"))
        connection.commit()
        
    if not inspector.has_table("conversations"):
        Conversation.__table__.create(connection)
    
    if not inspector.has_table("conversation_members"):
        ConversationMember.__table__.create(connection)
    else:
        cm_cols = [c['name'] for c in inspector.get_columns('conversation_members')]
        if 'id' not in cm_cols:
            try:
                data = connection.execute(text("SELECT * FROM conversation_members")).mappings().all()
                connection.execute(text("DROP TABLE conversation_members;"))
                ConversationMember.__table__.create(connection)
                if data:
                    insert_stmt = ConversationMember.__table__.insert()
                    for row in data:
                        row_data = {k: v for k, v in row.items() if k in cm_cols} 
                        connection.execute(insert_stmt.values(row_data))
                connection.commit()
            except Exception as e:
                connection.rollback()

    if inspector.has_table("direct_messages"):
        dm_columns = [col['name'] for col in inspector.get_columns('direct_messages')]
        if 'conversation_id' not in dm_columns:
            try:
                connection.execute(text("ALTER TABLE direct_messages ADD COLUMN conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE"))
            except Exception as e:
                pass
        
        dm_cols_full = inspector.get_columns('direct_messages')
        receiver_col_info = next((c for c in dm_cols_full if c['name'] == 'receiver_id'), None)
        
        if receiver_col_info and not receiver_col_info.get('nullable'):
            try:
                data = connection.execute(text("SELECT * FROM direct_messages")).mappings().all()
                connection.execute(text("DROP TABLE direct_messages;"))
                DirectMessage.__table__.create(connection)
                if data:
                    new_cols = [c.name for c in DirectMessage.__table__.columns]
                    insert_stmt = DirectMessage.__table__.insert()
                    for row in data:
                        row_data = {k: v for k, v in row.items() if k in new_cols}
                        for date_field in ['sent_at', 'read_at']:
                            if date_field in row_data and isinstance(row_data[date_field], str):
                                try: row_data[date_field] = datetime.fromisoformat(row_data[date_field])
                                except: pass
                        connection.execute(insert_stmt.values(row_data))
                connection.commit()
            except Exception as e:
                connection.rollback()

    if not inspector.has_table("note_groups"):
        NoteGroup.__table__.create(connection)
        connection.commit()

    if not inspector.has_table("notes"):
        Note.__table__.create(connection)
        connection.commit()

    connection.commit()


def check_and_update_db_version(SessionLocal):
    session = SessionLocal()
    try:
        version_record = session.query(DatabaseVersion).filter_by(id=1).first()
        if not version_record:
            new_version_record = DatabaseVersion(id=1, version=CURRENT_DB_VERSION) 
            session.add(new_version_record)
            session.commit()
        elif version_record.version != CURRENT_DB_VERSION: 
            version_record.version = CURRENT_DB_VERSION 
            session.commit()
    except Exception as e_ver:
        session.rollback()
    finally:
        session.close()

def _migrate_user_data_folders(connection):
    users_root_path = APP_DATA_DIR / USERS_DIR_NAME
    users_root_path.mkdir(exist_ok=True)
    try:
        usernames = {row[0] for row in connection.execute(text("SELECT username FROM users")).fetchall()}
        non_user_folders = {USERS_DIR_NAME, "cache", "zoo", "apps", "mcps", "custom_apps", "apps_zoo", "mcps_zoo", "prompts_zoo", "personalities_zoo", "huggingface_cache"}
        for item in APP_DATA_DIR.iterdir():
            if item.is_dir() and item.name in usernames and item.name not in non_user_folders:
                old_path = item
                new_path = users_root_path / item.name
                if not new_path.exists():
                    try: shutil.move(str(old_path), str(new_path))
                    except Exception: pass
    except Exception: pass
