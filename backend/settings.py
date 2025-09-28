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
                    final_value = None
                    try:
                        # First, assume it's our structured format: {"value": ..., "type": ...}
                        structured_data = json.loads(config.value)
                        
                        # Handle cases where the JSON is double-encoded (stored as a string within a string)
                        if isinstance(structured_data, str):
                            structured_data = json.loads(structured_data)

                        if isinstance(structured_data, dict) and 'value' in structured_data and 'type' in structured_data:
                            val = structured_data['value']
                            val_type = structured_data['type']
                            
                            try:
                                if val_type == 'integer':
                                    final_value = int(val)
                                elif val_type == 'float':
                                    final_value = float(val)
                                elif val_type == 'boolean':
                                    final_value = str(val).lower() in ('true', '1', 'yes', 'on')
                                else:
                                    final_value = val
                            except (ValueError, TypeError):
                                final_value = val  # Fallback to the raw value if casting fails
                        else:
                            # It's a valid JSON value, but not our structured format. Use it as is.
                            final_value = structured_data
                    except (json.JSONDecodeError, TypeError):
                        # The value is not a valid JSON string, use it as a raw string.
                        final_value = config.value
                    
                    self._settings_cache[config.key] = final_value

                print(f"INFO: Loaded {len(self._settings_cache)} settings into cache.")
            self._is_loaded = True
        except Exception as e:
            print(f"CRITICAL: An unexpected error occurred while loading settings: {e}.")
            self._is_loaded = False # Ensure we can try again if it fails

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        if not self._is_loaded:
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