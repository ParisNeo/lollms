import json
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from backend.db.models.config import GlobalConfig

class _Settings:
    _instance = None
    _settings_cache: Dict[str, Any] = {}
    _is_loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(_Settings, cls).__new__(cls)
        return cls._instance

    def load_from_db(self, db: Session):
        """
        Loads all settings from the database into the cache.
        This method is called explicitly at startup.
        """
        if self._is_loaded:
            return

        print("INFO: Loading global settings from database into cache...")
        try:
            configs = db.query(GlobalConfig).all()
            if not configs:
                print("WARNING: No settings found in 'global_configs' table.")
                self._settings_cache = {}
            else:
                for config in configs:
                    current_value = config.value
                    
                    while isinstance(current_value, str):
                        try:
                            current_value = json.loads(current_value)
                        except (json.JSONDecodeError, TypeError):
                            break

                    final_value = current_value
                    
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
                            else:
                                final_value = str(val)
                        except (ValueError, TypeError):
                            final_value = val
                    
                    self._settings_cache[config.key] = final_value
                print(f"INFO: Loaded {len(self._settings_cache)} settings into cache.")
            self._is_loaded = True
        except Exception as e:
            print(f"CRITICAL: An unexpected error occurred while loading settings: {e}.")
            self._is_loaded = False

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        if not self._is_loaded:
            # This should ideally not happen after startup, but it's a safe fallback.
            print("WARNING: Settings accessed before being loaded. This may indicate an issue.")
        return self._settings_cache.get(key, default)

    def all(self) -> Dict[str, Any]:
        return self._settings_cache.copy()

    def refresh(self, db: Session):
        """Forces a reload of the settings from the database."""
        print("INFO: Refreshing global settings cache from database...")
        self._is_loaded = False
        self._settings_cache.clear()
        self.load_from_db(db)

settings = _Settings()