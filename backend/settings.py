# backend/settings.py
# -*- coding: utf-8 -*-
# Project name: simplified_lollms
# File path: backend/settings.py
# Description: Manages global application settings loaded from the database.

import json
from typing import Any, Dict, Optional

# --- DO NOT import database modules at the top level here to avoid circular imports ---

class _Settings:
    """
    A singleton class to hold and manage global application settings.
    Settings are loaded from the database on first access and cached for performance.
    """
    _instance = None
    _settings_cache: Dict[str, Any] = {}
    _is_loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(_Settings, cls).__new__(cls)
        return cls._instance

    def _ensure_loaded(self):
        """
        Internal method to load settings from the DB if they haven't been loaded yet.
        Imports are done locally within the method to prevent circular dependencies.
        """
        if self._is_loaded:
            return

        # --- MODIFIED: Imports are now local to this method ---
        from backend.database_setup import GlobalConfig, get_db
        from sqlalchemy.orm import Session
        from sqlalchemy.exc import OperationalError

        print("INFO: First access to settings: Initializing and loading from database...")
        db_gen = None
        try:
            db_gen = get_db()
            db: Session = next(db_gen)
            configs = db.query(GlobalConfig).all()
            if not configs:
                print("WARNING: No settings found in 'global_configs' table. Application may use hardcoded defaults. This is normal on first-ever startup before bootstrap completes.")
                self._settings_cache = {}
            else:
                for config in configs:
                    try:
                        stored_data = json.loads(config.value)
                        self._settings_cache[config.key] = stored_data.get('value')
                    except (json.JSONDecodeError, TypeError) as e:
                        print(f"ERROR: Could not parse setting '{config.key}'. Stored value: {config.value}. Error: {e}")
                print(f"INFO: Loaded {len(self._settings_cache)} settings into cache.")
            self._is_loaded = True
        except StopIteration:
            print("CRITICAL: Failed to get a database session. Settings cannot be loaded.")
            self._is_loaded = False
        except OperationalError as e:
            print(f"CRITICAL: A database operational error occurred while loading settings: {e}. Check database connection and schema.")
            self._is_loaded = False
        except Exception as e:
            print(f"CRITICAL: An unexpected error occurred while loading settings from database: {e}.")
            self._is_loaded = False
        finally:
            if db_gen:
                try:
                    # Attempt to close the database session
                    next(db_gen, None)
                except StopIteration:
                    # This is expected if the session was already consumed and closed
                    pass

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """
        Retrieves a setting value by its key from the cache.
        """
        self._ensure_loaded()
        return self._settings_cache.get(key, default)

    def all(self) -> Dict[str, Any]:
        """
        Returns a copy of all cached settings.
        """
        self._ensure_loaded()
        return self._settings_cache.copy()

    def refresh(self):
        """
        Forces a reload of the settings from the database.
        """
        print("INFO: Refreshing global settings cache from database...")
        self._is_loaded = False
        self._settings_cache.clear()
        self._ensure_loaded()

# Create a single, globally-accessible instance of the settings manager.
settings = _Settings()