import yaml
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Literal
from sqlalchemy.orm import Session
from backend.db import get_db
from backend.db.models.service import AppZooRepository, MCPZooRepository, PromptZooRepository
from backend.db.models.prompt import SavedPrompt
from backend.config import APPS_ZOO_ROOT_PATH, MCPS_ZOO_ROOT_PATH, PROMPTS_ZOO_ROOT_PATH, APP_DATA_DIR

ITEM_TYPES = Literal['app', 'mcp', 'prompt']
CACHE_FILE = APP_DATA_DIR / "zoo_cache.json"
CACHE_EXPIRY = 3600  # 1 hour

_cache: Dict[str, Any] = {"timestamp": 0, "data": {}}

def get_zoo_root_path(item_type: ITEM_TYPES) -> Path:
    if item_type == 'app': return APPS_ZOO_ROOT_PATH
    if item_type == 'mcp': return MCPS_ZOO_ROOT_PATH
    if item_type == 'prompt': return PROMPTS_ZOO_ROOT_PATH
    raise ValueError(f"Invalid item type: {item_type}")

def get_db_repo_model(item_type: ITEM_TYPES):
    if item_type == 'app': return AppZooRepository
    if item_type == 'mcp': return MCPZooRepository
    if item_type == 'prompt': return PromptZooRepository
    raise ValueError(f"Invalid item type: {item_type}")

def get_installed_items(db: Session, item_type: ITEM_TYPES) -> set:
    if item_type in ['app', 'mcp']:
        from backend.db.models.service import App as DBApp
        return {item.name for item in db.query(DBApp.name).filter(DBApp.is_installed == True, DBApp.app_metadata['item_type'].as_string() == item_type).all()}
    if item_type == 'prompt':
        return {item.name for item in db.query(SavedPrompt.name).filter(SavedPrompt.owner_user_id.is_(None)).all()}
    return set()

def parse_item_metadata(item_path: Path, item_type: ITEM_TYPES) -> Dict[str, Any]:
    metadata = {}
    if item_type in ['app', 'mcp']:
        config_path = item_path / "config.yaml"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                metadata = yaml.safe_load(f)
    elif item_type == 'prompt':
        desc_path = item_path / "description.yaml"
        prompt_path = item_path / "prompt.txt"
        if desc_path.exists() and prompt_path.exists():
            with open(desc_path, 'r', encoding='utf-8') as f:
                metadata = yaml.safe_load(f) or {}
            # The prompt content itself is not needed for the listing, only for installation.
    return metadata

def _build_cache_for_type(db: Session, item_type: ITEM_TYPES) -> List[Dict[str, Any]]:
    items = []
    zoo_root = get_zoo_root_path(item_type)
    repo_model = get_db_repo_model(item_type)
    
    repositories = db.query(repo_model).all()
    
    for repo in repositories:
        repo_path = zoo_root / repo.name
        if not repo_path.is_dir(): continue
        
        for item_folder in repo_path.iterdir():
            if item_folder.is_dir() and not item_folder.name.startswith('.'):
                try:
                    metadata = parse_item_metadata(item_folder, item_type)
                    if not metadata or not metadata.get('name'):
                        metadata['name'] = item_folder.name
                    
                    icon_path_png = item_folder / "icon.png"
                    icon_b64 = None
                    if icon_path_png.exists():
                        import base64
                        with open(icon_path_png, 'rb') as f:
                            icon_b64 = f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"

                    items.append({
                        **metadata,
                        'repository': repo.name,
                        'folder_name': item_folder.name,
                        'icon': icon_b64
                    })
                except Exception as e:
                    print(f"Warning: Could not process {item_type} item '{item_folder.name}' in repo '{repo.name}': {e}")
    return items

def build_full_cache():
    global _cache
    print("INFO: Building full Zoo cache...")
    db = next(get_db())
    try:
        _cache["data"] = {
            'app': _build_cache_for_type(db, 'app'),
            'mcp': _build_cache_for_type(db, 'mcp'),
            'prompt': _build_cache_for_type(db, 'prompt'),
        }
        _cache["timestamp"] = time.time()
        with open(CACHE_FILE, 'w') as f:
            json.dump(_cache, f)
        print("INFO: Zoo cache rebuild complete.")
    finally:
        db.close()

def refresh_repo_cache(repo_name: str, item_type: ITEM_TYPES):
    global _cache
    if not _cache["data"]:
        load_cache()
    
    # Remove old items from this repo
    _cache["data"][item_type] = [item for item in _cache["data"].get(item_type, []) if item.get('repository') != repo_name]
    
    # Add new items from this repo
    db = next(get_db())
    try:
        repo = db.query(get_db_repo_model(item_type)).filter_by(name=repo_name).first()
        if repo:
            repo_path = get_zoo_root_path(item_type) / repo.name
            if repo_path.is_dir():
                for item_folder in repo_path.iterdir():
                    if item_folder.is_dir() and not item_folder.name.startswith('.'):
                        try:
                            metadata = parse_item_metadata(item_folder, item_type)
                            if not metadata.get('name'): metadata['name'] = item_folder.name
                            icon_path_png = item_folder / "icon.png"
                            icon_b64 = None
                            if icon_path_png.exists():
                                import base64
                                with open(icon_path_png, 'rb') as f: icon_b64 = f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"
                            
                            _cache["data"][item_type].append({**metadata, 'repository': repo.name, 'folder_name': item_folder.name, 'icon': icon_b64})
                        except Exception as e:
                            print(f"Warning: Could not process item '{item_folder.name}' on refresh: {e}")

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
