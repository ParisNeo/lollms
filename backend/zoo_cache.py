import base64
import yaml
import threading
from pathlib import Path
from typing import Dict, List, Any

from backend.config import APPS_ZOO_ROOT_PATH, MCPS_ZOO_ROOT_PATH

_app_zoo_cache: Dict[str, List[Dict[str, Any]]] = {}
_mcp_zoo_cache: Dict[str, List[Dict[str, Any]]] = {}
_cache_lock = threading.Lock()

def _scan_zoo_directory(zoo_root_path: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Scans a full zoo directory and returns structured metadata."""
    repo_data = {}
    if not zoo_root_path.exists():
        return {}

    for repo_dir in zoo_root_path.iterdir():
        if repo_dir.is_dir():
            repo_items = []
            for item_dir in repo_dir.iterdir():
                info_file_path = None
                if (item_dir / "app_info.yaml").is_file():
                    info_file_path = item_dir / "app_info.yaml"
                elif (item_dir / "description.yaml").is_file():
                    info_file_path = item_dir / "description.yaml"

                if item_dir.is_dir() and info_file_path:
                    try:
                        with open(info_file_path, "r", encoding='utf-8') as f:
                            info = yaml.safe_load(f)
                            if info and isinstance(info, dict) and 'name' in info:
                                info['repository'] = repo_dir.name
                                info['folder_name'] = item_dir.name
                                
                                # Add icon data URL to cache
                                icon_path = None
                                if (item_dir / "assets" / "logo.png").is_file():
                                    icon_path = item_dir / "assets" / "logo.png"
                                elif (item_dir / "icon.png").is_file():
                                    icon_path = item_dir / "icon.png"
                                
                                if icon_path:
                                    info['icon'] = f"data:image/png;base64,{base64.b64encode(icon_path.read_bytes()).decode()}"

                                repo_items.append(info)
                    except Exception as e:
                        print(f"Warning: Could not parse metadata for {item_dir.name}. Error: {e}")
            repo_data[repo_dir.name] = repo_items
    return repo_data

def build_full_cache():
    """Builds or rebuilds the entire in-memory cache for both App and MCP Zoos."""
    print("INFO: Building full Zoo metadata cache...")
    with _cache_lock:
        global _app_zoo_cache, _mcp_zoo_cache
        _app_zoo_cache = _scan_zoo_directory(APPS_ZOO_ROOT_PATH)
        _mcp_zoo_cache = _scan_zoo_directory(MCPS_ZOO_ROOT_PATH)
    print("INFO: Zoo metadata cache build complete.")

def refresh_repo_cache(repo_name: str, item_type: str):
    """Refreshes the cache for a single repository."""
    print(f"INFO: Refreshing cache for '{repo_name}' ({item_type} zoo)...")
    zoo_path = APPS_ZOO_ROOT_PATH if item_type == 'app' else MCPS_ZOO_ROOT_PATH
    target_cache = _app_zoo_cache if item_type == 'app' else _mcp_zoo_cache

    repo_dir = zoo_path / repo_name
    if not repo_dir.is_dir():
        with _cache_lock:
            if repo_name in target_cache:
                del target_cache[repo_name]
        print(f"INFO: Repository '{repo_name}' removed from cache.")
        return

    # Rescan just this one repository
    scanned_data = _scan_zoo_directory(repo_dir.parent)
    
    with _cache_lock:
        if repo_name in scanned_data:
            target_cache[repo_name] = scanned_data[repo_name]
        elif repo_name in target_cache: # It might have been valid before but now is empty/invalid
            del target_cache[repo_name]

    print(f"INFO: Cache for '{repo_name}' refreshed.")


def get_all_items(item_type: str) -> List[Dict[str, Any]]:
    """Gets all items of a specific type, deduplicating by name."""
    with _cache_lock:
        source_cache = _app_zoo_cache if item_type == 'app' else _mcp_zoo_cache
        all_items_dict = {}
        # Flatten and deduplicate. The last one found wins in case of conflict.
        for repo_items in source_cache.values():
            for item in repo_items:
                all_items_dict[item['name']] = item
    return list(all_items_dict.values())

def get_all_categories(item_type: str) -> List[str]:
    """Gets all unique categories for a given item type from the cache."""
    all_items = get_all_items(item_type)
    categories = {item.get('category', 'Uncategorized') for item in all_items if item.get('category')}
    return sorted(list(categories))
