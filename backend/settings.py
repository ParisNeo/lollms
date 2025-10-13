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
        This method is now safe to be called by multiple processes; it will only execute
        the loading and logging logic once per process lifecycle thanks to the _is_loaded flag.
        """
        if self._is_loaded:
            return

        try:
            configs = db.query(GlobalConfig).all()
            if not configs:
                print("WARNING: No settings found in 'global_configs' table.")
                self._settings_cache = {}
            else:
                for config in configs:
                    try:
                        # Value from DB is expected to be a JSON string like '{"value": ..., "type": ...}'
                        structured_data = json.loads(config.value)
                        
                        # Handle case where the value itself is a JSON string (double-encoded)
                        if isinstance(structured_data, str):
                            structured_data = json.loads(structured_data)
                        
                        # Now, we should have a dict. Extract the actual value.
                        if isinstance(structured_data, dict) and 'value' in structured_data:
                            val = structured_data.get('value')
                            val_type = structured_data.get('type', 'string')

                            if val_type == 'integer':
                                self._settings_cache[config.key] = int(val) if val is not None else 0
                            elif val_type == 'float':
                                self._settings_cache[config.key] = float(val) if val is not None else 0.0
                            elif val_type == 'boolean':
                                self._settings_cache[config.key] = str(val).lower() in ('true', '1', 'yes', 'on')
                            elif val_type == 'json':
                                if isinstance(val, str):
                                    self._settings_cache[config.key] = json.loads(val) if val else {}
                                else:
                                    self._settings_cache[config.key] = val  # It's already a dict/list
                            else:  # string, text, etc.
                                self._settings_cache[config.key] = val
                        else:
                            # Fallback for old/unstructured JSON data (e.g., just "some_value" or a raw JSON dict)
                            self._settings_cache[config.key] = structured_data
                    except (json.JSONDecodeError, TypeError, ValueError):
                        # If it's not valid JSON, treat it as a raw string
                        self._settings_cache[config.key] = config.value

            print(f"INFO: Loaded {len(self._settings_cache)} settings into cache.")
            self._is_loaded = True
        except Exception as e:
            print(f"CRITICAL: An unexpected error occurred while loading settings: {e}.")
            self._is_loaded = False

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        if not self._is_loaded:
            print("WARNING: Settings accessed before being loaded. This may indicate an issue.")
        
        value = self._settings_cache.get(key, default)
        
        # FINAL SAFEGUARD: If a dictionary wrapper was somehow cached, extract the primitive value.
        if isinstance(value, dict) and 'value' in value:
            return value['value']
            
        return value

    def all(self) -> Dict[str, Any]:
        return self._settings_cache.copy()

    def refresh(self, db: Session):
        """Forces a reload of the settings from the database."""
        print("INFO: Refreshing global settings cache from database...")
        self._is_loaded = False
        self._settings_cache.clear()
        self.load_from_db(db)

settings = _Settings()