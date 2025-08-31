# backend/routers/discussion.py
# Standard Library Imports
import base64
import io
import json
import re
import shutil
import uuid
from datetime import datetime
from typing import Dict, List, Optional
import threading

# Third-Party Imports
import fitz  # PyMuPDF
from fastapi import (
    APIRouter, BackgroundTasks, Depends, HTTPException, Query)
from sqlalchemy.orm import Session
from ascii_colors import ASCIIColors, trace_exception

# Local Application Imports
from backend.db import get_db
from backend.db.models.user import (User as DBUser, UserMessageGrade,
                                     UserStarredDiscussion)
from backend.discussion import get_user_discussion, get_user_discussion_manager
from backend.models import (UserAuthDetails, DiscussionBranchSwitchRequest,
                            DiscussionInfo, DiscussionTitleUpdate, MessageOutput
                            )
from backend.session import (get_current_active_user,
                             get_user_discussion_assets_path,
                            )

# safe_store is needed for RAG callbacks
def 
message_grade_lock = threading.Lock()


