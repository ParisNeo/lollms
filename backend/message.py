# --- Helpers ---
# Standard Library Imports
import os
import shutil
import uuid
import json
from pathlib import Path
from typing import List, Dict, Optional, Any, cast, Union, Tuple, AsyncGenerator
import datetime
import asyncio
import threading
import traceback
import io

# Third-Party Imports
import toml
import yaml
from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    Request,
    File,
    UploadFile,
    Form,
    APIRouter,
    Response,
    Query,
    BackgroundTasks
)
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import (
    HTMLResponse,
    StreamingResponse,
    JSONResponse,
    FileResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, constr, field_validator, validator
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import (
    or_, and_ # Add this line
)
from dataclasses import dataclass, field as dataclass_field
from werkzeug.utils import secure_filename
from pydantic import BaseModel, Field, constr, field_validator, validator # Ensure these are imported
import datetime # Ensure datetime is imported

from backend.database_setup import Personality as DBPersonality # Add this import at the top of main.py
from backend.config import *
# --- Pydantic Models for API ---
from backend.models import (
UserLLMParams,
UserAuthDetails,
UserCreateAdmin,
UserPasswordResetAdmin,UserPasswordChange,
UserPublic,
DiscussionInfo,
DiscussionTitleUpdate,
DiscussionRagDatastoreUpdate,MessageOutput,
MessageContentUpdate,
MessageGradeUpdate,
SafeStoreDocumentInfo,
DiscussionExportRequest,
ExportData,
DiscussionImportRequest,
DiscussionSendRequest,
DataStoreBase,
DataStoreCreate,
DataStorePublic,
DataStoreShareRequest,
PersonalityBase,
PersonalityCreate,
PersonalityUpdate,
PersonalityPublic,
UserUpdate,
FriendshipBase,
FriendRequestCreate,
FriendshipAction,
FriendPublic,
FriendshipRequestPublic,
PersonalitySendRequest,

DirectMessagePublic,
DirectMessageCreate
)
# safe_store is expected to be installed
try:
    import safe_store
    from safe_store import (
        LogLevel as SafeStoreLogLevel,
    )
except ImportError:
    print(
        "WARNING: safe_store library not found. RAG features will be disabled. Install with: pip install safe_store[all]"
    )
    safe_store = None
    SafeStoreLogLevel = None


@dataclass
class AppLollmsMessage:
    """Represents a single message with enriched metadata for persistence."""
    sender: str
    content: str
    id: str = dataclass_field(default_factory=lambda: str(uuid.uuid4()))
    parent_message_id: Optional[str] = None
    created_at: datetime.datetime = dataclass_field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)) # NEW: Added for sorting and display
    binding_name: Optional[str] = None
    model_name: Optional[str] = None
    token_count: Optional[int] = None    
    sources: Optional[List[Dict]] = None # FIXED: Should be a list of dicts for multiple sources
    image_references: Optional[List[str]] = dataclass_field(default_factory=list) # Stores paths relative to user_discussion_assets_path / discussion_id

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the message object to a dictionary for saving."""
        data = {
            "id": self.id,
            "sender": self.sender,
            "content": self.content,
            "parent_message_id": self.parent_message_id,
            "created_at": self.created_at.isoformat(), # FIXED: Serialize timestamp to ISO string
            "binding_name": self.binding_name,
            "model_name": self.model_name,
            "token_count": self.token_count,
            "sources": self.sources, # FIXED: Include sources
            "image_references": self.image_references or [],
        }
        # Clean up None values for a cleaner YAML/JSON output
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppLollmsMessage":
        """Deserializes a dictionary into a message object."""
        # FIXED: Handle deserialization of the timestamp
        created_at_val = data.get("created_at")
        if isinstance(created_at_val, str):
            try:
                created_at = datetime.datetime.fromisoformat(created_at_val)
            except ValueError:
                # Fallback for older formats or parsing errors
                created_at = datetime.datetime.now(datetime.timezone.utc)
        else:
            # If no timestamp, create one now (useful for migrating old data)
            created_at = datetime.datetime.now(datetime.timezone.utc)

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            sender=data.get("sender", "unknown"),
            content=data.get("content", ""),
            parent_message_id=data.get("parent_message_id"),
            created_at=created_at,
            binding_name=data.get("binding_name"),
            model_name=data.get("model_name"),
            token_count=data.get("token_count"),
            sources=data.get("sources"), # FIXED: Include sources
            image_references=data.get("image_references", [])
        )