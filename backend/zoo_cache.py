import yaml
import json
import time
from pathlib import Path
import base64
from typing import List, Dict, Any, Literal
from sqlalchemy.orm import Session
from backend.db import get_db
from backend.db.models.service import AppZooRepository, MCPZooRepository, PromptZooRepository, PersonalityZooRepository
from backend.db.models.prompt import SavedPrompt
from backend.db.models.personality import Personality
from backend.config import APPS_ZOO_ROOT_PATH, MCPS_ZOO_ROOT_PATH, PROMPTS_ZOO_ROOT_PATH, PERSONALITIES_ZOO_ROOT_PATH, APP_DATA_DIR
import datetime
from ascii_colors import ASCIIColors

ITEM_TYPES = Literal['app', 'mcp', 'prompt', 'personality']
CACHE_FILE = APP_DATA_DIR / "zoo_cache.json"
CACHE_EXPIRY = 3600  # 1 hour

_cache: Dict[str, Any] = {"timestamp": 0, "data": {}}

def _sanitize_for_json(data: Any) -> Any:
    """Recursively sanitizes data to ensure it's JSON serializable."""
    if isinstance(data, (datetime.datetime, datetime.date)):
        return data.isoformat()
    if isinstance(data, dict):
        return {k: _sanitize_for_json(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_sanitize_for_json(v) for v in data]
    return data

def get_zoo_root_path(item_type: ITEM_TYPES) -> Path:
    if item_type == 'app': return APPS_ZOO_ROOT_PATH
    if item_type == 'mcp': return MCPS_ZOO_ROOT_PATH
    if item_type == 'prompt': return PROMPTS_ZOO_ROOT_PATH
    if item_type == 'personality': return PERSONALITIES_ZOO_ROOT_PATH
    raise ValueError(f"Invalid item type: {item_type}")

def get_db_repo_model(item_type: ITEM_TYPES):
    if item_type == 'app': return AppZooRepository
    if item_type == 'mcp': return MCPZooRepository
    if item_type == 'prompt': return PromptZooRepository
    if item_type == 'personality': return PersonalityZooRepository
    raise ValueError(f"Invalid item type: {item_type}")

def get_installed_items(db: Session, item_type: ITEM_TYPES) -> set:
    if item_type in ['app', 'mcp']:
        from backend.db.models.service import App as DBApp
        return {item.name for item in db.query(DBApp.name).filter(DBApp.is_installed == True, DBApp.app_metadata['item_type'].as_string() == item_type).all()}
    if item_type == 'prompt':
        return {item.name for item in db.query(SavedPrompt.name).filter(SavedPrompt.owner_user_id.is_(None)).all()}
    if item_type == 'personality':
        return {item.name for item in db.query(Personality.name).filter(Personality.owner_user_id.is_(None)).all()}
    return set()

def parse_item_metadata(item_path: Path, item_type: ITEM_TYPES) -> Dict[str, Any]:
    metadata = {}
    if item_type == 'personality':
        desc_path = item_path / "description.yaml"
        conf_path = item_path / "config.yaml"
        if desc_path.exists():
            with open(desc_path, 'r', encoding='utf-8') as f:
                metadata = yaml.safe_load(f) or {}
        elif conf_path.exists():
            with open(conf_path, 'r', encoding='utf-8') as f:
                legacy_data = yaml.safe_load(f) or {}
            # Map legacy format to new format
            metadata = {
                'name': legacy_data.get('name'),
                'version': str(legacy_data.get('version', 'N/A')),
                'author': legacy_data.get('author'),
                'category': legacy_data.get('category'),
                'description': legacy_data.get('personality_description'),
                'prompt_text': legacy_data.get('personality_conditioning'),
                'disclaimer': legacy_data.get('disclaimer'),
                'active_mcps': legacy_data.get('dependencies', [])
            }
    else: # app, mcp, prompt
        config_path = item_path / "description.yaml"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                metadata = yaml.safe_load(f) or {}
    return metadata

def _build_cache_for_type(db: Session, item_type: ITEM_TYPES) -> List[Dict[str, Any]]:
    items = []
    zoo_root = get_zoo_root_path(item_type)
    repo_model = get_db_repo_model(item_type)
    
    repositories = db.query(repo_model).all()
    
    for repo in repositories:
        repo_path = None
        if repo.type == 'git':
            repo_path = zoo_root / repo.name
        elif repo.type == 'local':
            repo_path = Path(repo.url)
        else:
            continue

        if not repo_path or not repo_path.is_dir(): continue
        
        # Use glob to find all possible config files, supporting nested structures
        config_files = list(repo_path.glob('**/description.yaml'))
        if item_type == 'personality':
            config_files.extend(list(repo_path.glob('**/config.yaml')))

        for config_file in config_files:
            item_folder = config_file.parent
            try:
                metadata = parse_item_metadata(item_folder, item_type)
                if not metadata or not metadata.get('name'):
                    metadata['name'] = item_folder.name
                
                # --- FIX: Handle category being a list ---
                if 'category' in metadata and isinstance(metadata['category'], list):
                    metadata['category'] = metadata['category'][0] if metadata['category'] else 'Uncategorized'
                # --- END FIX ---
                
                # --- NEW: Detect legacy scripted personalities ---
                if item_type == 'personality' and (item_folder / "scripts" / "processor.py").exists():
                    metadata['is_legacy_scripted'] = True
                # --- END NEW ---

                # Icon handling
                icon_path = next((p for p in [item_folder / "icon.png", item_folder / "assets" / "logo.png"] if p.exists()), None)
                icon_b64 = None
                if icon_path:
                    with open(icon_path, 'rb') as f:
                        icon_b64 = f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"

                # Use relative path for folder_name to handle nested structures
                folder_name_rel = item_folder.relative_to(repo_path).as_posix()

                items.append(_sanitize_for_json({
                    **metadata,
                    'item_type': item_type,
                    'repository': repo.name,
                    'folder_name': folder_name_rel,
                    'icon': icon_b64
                }))
            except Exception as e:
                print(f"Warning: Could not process {item_type} item at '{item_folder}' in repo '{repo.name}': {e}")
    return items

def build_full_cache():
    global _cache
    ASCIIColors.info("INFO: Building full Zoo cache...")
    db = next(get_db())
    try:
        _cache["data"] = {
            'app': _build_cache_for_type(db, 'app'),
            'mcp': _build_cache_for_type(db, 'mcp'),
            'prompt': _build_cache_for_type(db, 'prompt'),
            'personality': _build_cache_for_type(db, 'personality'),
        }
        _cache["timestamp"] = time.time()
        with open(CACHE_FILE, 'w') as f:
            json.dump(_cache, f)
        print("INFO: Zoo cache rebuild complete.")
    finally:
        db.close()

def refresh_repo_cache(repo_name: str, item_type: ITEM_TYPES):
    global _cache
    if not _cache.get("data"):
        load_cache()
    
    if item_type not in _cache.get("data", {}):
        _cache["data"][item_type] = []
        
    _cache["data"][item_type] = [item for item in _cache["data"].get(item_type, []) if item.get('repository') != repo_name]
    
    db = next(get_db())
    try:
        repo = db.query(get_db_repo_model(item_type)).filter_by(name=repo_name).first()
        if repo:
            repo_path = None
            if repo.type == 'git': repo_path = get_zoo_root_path(item_type) / repo.name
            elif repo.type == 'local': repo_path = Path(repo.url)
            
            if repo_path and repo_path.is_dir():
                config_files = list(repo_path.glob('**/description.yaml'))
                if item_type == 'personality': config_files.extend(list(repo_path.glob('**/config.yaml')))

                for config_file in config_files:
                    item_folder = config_file.parent
                    try:
                        metadata = parse_item_metadata(item_folder, item_type)
                        if not metadata.get('name'): metadata['name'] = item_folder.name

                        # --- FIX: Handle category being a list (also needed for refresh) ---
                        if 'category' in metadata and isinstance(metadata['category'], list):
                            metadata['category'] = metadata['category'][0] if metadata['category'] else 'Uncategorized'
                        # --- END FIX ---
                        
                        # --- NEW: Detect legacy scripted personalities on refresh ---
                        if item_type == 'personality' and (item_folder / "scripts" / "processor.py").exists():
                            metadata['is_legacy_scripted'] = True
                        # --- END NEW ---

                        icon_path = next((p for p in [item_folder / "icon.png", item_folder / "assets" / "logo.png"] if p.exists()), None)
                        icon_b64 = None
                        if icon_path:
                            with open(icon_path, 'rb') as f: icon_b64 = f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"
                        
                        folder_name_rel = item_folder.relative_to(repo_path).as_posix()
                        
                        _cache["data"][item_type].append(_sanitize_for_json({**metadata, 'item_type': item_type, 'repository': repo.name, 'folder_name': folder_name_rel, 'icon': icon_b64}))
                    except Exception as e:
                        print(f"Warning: Could not process item '{item_folder}' on refresh: {e}")

        _cache["timestamp"] = time.time()
        with open(CACHE_FILE, 'w') as f: json.dump(_cache, f)
    finally:
        db.close()


def load_cache():
    global _cache
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r') as f:
                _cache = json.load(f)
        except (json.JSONDecodeError, TypeError):
            print("Warning: Could not load cache file. Rebuilding.")
            _cache = {"timestamp": 0, "data": {}}
    if time.time() - _cache.get("timestamp", 0) > CACHE_EXPIRY:
        build_full_cache()

def get_all_items(item_type: ITEM_TYPES) -> List[Dict[str, Any]]:
    load_cache()
    return _cache.get("data", {}).get(item_type, [])

def get_all_categories(item_type: ITEM_TYPES) -> List[str]:
    items = get_all_items(item_type)
    categories = {'All'}
    for item in items:
        if item.get('category'):
            categories.add(item['category'])
    return sorted(list(categories))