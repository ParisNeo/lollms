import json
from typing import Any, Dict, Optional

from backend.db import get_db
from backend.db.models.config import GlobalConfig

class _Settings:
    _instance = None
    _settings_cache: Dict[str, Any] = {}
    _is_loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(_Settings, cls).__new__(cls)
        return cls._instance

    def _ensure_loaded(self):
        if self._is_loaded:
            return

        from sqlalchemy.orm import Session
        from sqlalchemy.exc import OperationalError

        print("INFO: First access to settings: Initializing and loading from database...")
        db_gen = None
        try:
            db_gen = get_db()
            db: Session = next(db_gen)
            configs = db.query(GlobalConfig).all()
            if not configs:
                print("WARNING: No settings found in 'global_configs' table. This is normal on first-ever startup.")
                self._settings_cache = {}
            else:
                for config in configs:
                    current_value = config.value
                    
                    # Step 1: Recursively decode if value is a JSON string of another JSON string
                    while isinstance(current_value, str):
                        try:
                            current_value = json.loads(current_value)
                        except (json.JSONDecodeError, TypeError):
                            break  # Not a valid JSON string, so it's the final raw value

                    final_value = current_value
                    
                    # Step 2: If we ended up with our structured dictionary, extract and cast the inner value
                    if isinstance(final_value, dict) and 'value' in final_value and 'type' in final_value:
                        val = final_value['value']
                        val_type = final_value['type']
                        try:
                            if val_type == 'integer':
                                final_value = int(val)
                            elif val_type == 'float':
                                final_value = float(val)
                            elif val_type == 'boolean':
                                final_value = str(val).lower() in ('true', '1', 'yes', 'on')
                            else:  # string or any other type
                                final_value = str(val)
                        except (ValueError, TypeError):
                            # Fallback to the raw value if casting fails
                            final_value = val
                    
                    # Step 3: Store the final, primitive Python type in the cache
                    self._settings_cache[config.key] = final_value

                print(f"INFO: Loaded {len(self._settings_cache)} settings into cache.")
            self._is_loaded = True
        except StopIteration:
            print("CRITICAL: Failed to get a database session. Settings cannot be loaded.")
            self._is_loaded = False
        except OperationalError as e:
            print(f"CRITICAL: DB error during settings load: {e}. Check connection/schema.")
            self._is_loaded = False
        except Exception as e:
            print(f"CRITICAL: An unexpected error occurred while loading settings: {e}.")
            self._is_loaded = False
        finally:
            if db_gen:
                try:
                    next(db_gen, None)
                except StopIteration:
                    pass

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        self._ensure_loaded()
        return self._settings_cache.get(key, default)

    def all(self) -> Dict[str, Any]:
        self._ensure_loaded()
        return self._settings_cache.copy()

    def refresh(self):
        print("INFO: Refreshing global settings cache from database...")
        self._is_loaded = False
        self._settings_cache.clear()
        self._ensure_loaded()

settings = _Settings()