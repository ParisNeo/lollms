# backend/discussion.py
# Standard Library Imports
import os
import shutil
from pathlib import Path
from typing import List, Optional, Any, Dict, Set # Added Dict, Set for fix_lollms_discussion_orphans
import datetime
import uuid
import yaml
from dataclasses import dataclass, field as dataclass_field
from lollms_client import LollmsClient, LollmsDataManager, LollmsDiscussion, LollmsMessage
from ascii_colors import ASCIIColors

from backend.session import user_sessions, get_user_data_root, get_user_lollms_client

@dataclass
class _LegacyMessage:
    sender: str
    sender_type: str
    content: str
    id: str = dataclass_field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: Optional[str] = None
    created_at: datetime.datetime = dataclass_field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    binding_name: Optional[str] = None
    model_name: Optional[str] = None
    token_count: Optional[int] = None
    sources: Optional[List[Any]] = None
    steps: Optional[List[Any]] = None
    image_references: Optional[List[str]] = dataclass_field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "_LegacyMessage":
        created_at_val = data.get("created_at")
        if isinstance(created_at_val, str):
            try: created_at = datetime.datetime.fromisoformat(created_at_val)
            except ValueError: created_at = datetime.datetime.now(datetime.timezone.utc)
        else: created_at = datetime.datetime.now(datetime.timezone.utc)
        
        sender = data.get("sender", "unknown")
        sender_type = data.get("sender_type", "user" if sender not in ["lollms", "assistant"] else "assistant")

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            sender=sender,
            sender_type=sender_type,
            content=data.get("content", ""),
            parent_id=data.get("parent_message_id"), 
            created_at=created_at,
            binding_name=data.get("binding_name"),
            model_name=data.get("model_name"),
            token_count=data.get("token_count"),
            sources=data.get("sources",[]),
            steps=data.get("steps",[]),
            image_references=data.get("image_references", [])
        )

class LegacyDiscussion:
    def __init__(self, discussion_id: Optional[str] = None, title: Optional[str] = None):
        self.messages: List[_LegacyMessage] = []
        self.discussion_id: str = discussion_id or str(uuid.uuid4())
        self.title: str = title or f"Imported {self.discussion_id[:8]}"
        self.rag_datastore_ids: Optional[list] = None
        self.active_branch_id: Optional[str] = None

    @staticmethod
    def load_from_yaml(file_path: Path) -> Optional["LegacyDiscussion"]:
        if not file_path.exists(): return None
        try:
            with open(file_path, "r", encoding="utf-8") as file: data = yaml.safe_load(file)
        except Exception: return None

        if not isinstance(data, dict):
            discussion = LegacyDiscussion(discussion_id=file_path.stem)
            if isinstance(data, list):
                for msg_data in data:
                    if isinstance(msg_data, dict): discussion.messages.append(_LegacyMessage.from_dict(msg_data))
            return discussion

        discussion = LegacyDiscussion(discussion_id=data.get("discussion_id", file_path.stem), title=data.get("title"))
        discussion.rag_datastore_ids = data.get("rag_datastore_ids")
        discussion.active_branch_id = data.get("active_branch_id")
        
        for msg_data in data.get("messages", []):
            if isinstance(msg_data, dict): discussion.messages.append(_LegacyMessage.from_dict(msg_data))
        return discussion

def get_user_discussion_manager(username: str) -> LollmsDataManager:
    if "discussion_manager" in user_sessions.get(username, {}):
        manager = user_sessions[username].get("discussion_manager")
        if manager: return manager

    user_data_path = get_user_data_root(username)
    db_path = user_data_path / "discussions.db"
    db_url = f"sqlite:///{db_path.resolve()}"
    manager = LollmsDataManager(db_path=db_url)
    
    if username in user_sessions:
        user_sessions[username]["discussion_manager"] = manager
    else:
        user_sessions[username] = {"discussion_manager": manager}
    return manager

def fix_lollms_discussion_orphans(discussion: LollmsDiscussion):
    """
    Detects and re-chains orphan messages or branches in a LollmsDiscussion.
    
    An "orphan message" is one whose parent_id points to a message that
    does not exist in the discussion, or whose lineage cannot be traced
    back to a root message (parent_id is None) within the current discussion.

    This method attempts to reconnect such messages by:
    1. Identifying all messages and their parent-child relationships.
    2. Finding the true root message(s) of the discussion.
    3. Identifying all reachable messages from the true root(s).
    4. Any message not reachable is considered an orphan.
    5. For each orphan, traces up to find its "orphan branch top"
       (the highest message in its disconnected chain).
    6. Re-parents these orphan branch tops to the main discussion's
       primary root (the oldest root message). If no primary root exists,
       the oldest orphan branch top becomes the new primary root.
    """
    ASCIIColors.info(f"Checking discussion {discussion.id} for orphan messages...")

    all_messages: List[LollmsMessage] = discussion.get_all_messages_flat()
    if not all_messages:
        ASCIIColors.info(f"Discussion {discussion.id} is empty. No orphans to fix.")
        return

    message_map: Dict[str, LollmsMessage] = {msg.id: msg for msg in all_messages}
    
    # Adjacency list: parent_id -> [child_ids]
    children_map: Dict[Optional[str], List[str]] = {None: []} # For true roots
    
    for msg in all_messages:
        if msg.parent_id not in children_map:
            children_map[msg.parent_id] = []
        children_map[msg.parent_id].append(msg.id)

    # Identify all root messages (parent_id is None OR parent_id points to a non-existent message)
    potential_roots: List[LollmsMessage] = []
    for msg in all_messages:
        if msg.parent_id is None or msg.parent_id not in message_map:
            potential_roots.append(msg)
    
    # Sort potential roots by creation time to find the oldest true root
    potential_roots.sort(key=lambda m: m.created_at or datetime.datetime.min)

    main_root_id: Optional[str] = None
    if potential_roots:
        main_root_msg = potential_roots[0]
        main_root_id = main_root_msg.id
        # Ensure the main_root_id message itself has parent_id=None if it's not already.
        if main_root_msg.parent_id is not None:
             ASCIIColors.warning(f"Reparenting primary root {main_root_id} to None (was {main_root_msg.parent_id}).")
             discussion.update_message(main_root_id, parent_id=None)
             discussion.commit() # Commit this early change if the root itself was faulty
        
        ASCIIColors.info(f"Identified primary root: {main_root_id} (content: '{message_map[main_root_id].content[:50]}...')")
    else:
        # This scenario implies a discussion without any message satisfying the root criteria.
        # Make the very oldest message the main root, forcing its parent_id to None.
        if all_messages:
            oldest_message = min(all_messages, key=lambda m: m.created_at or datetime.datetime.min)
            if oldest_message.parent_id is not None:
                ASCIIColors.warning(f"No valid root found. Reparenting oldest message '{oldest_message.id}' to be the main root.")
                discussion.update_message(oldest_message.id, parent_id=None)
                discussion.commit()
                main_root_id = oldest_message.id
            else:
                main_root_id = oldest_message.id
        
        if not main_root_id:
            ASCIIColors.warning(f"Could not identify a main root for discussion {discussion.id}. Skipping orphan fixing.")
            return

    # Perform BFS from the main root to find all reachable messages
    reachable_message_ids: Set[str] = set()
    queue: List[str] = [main_root_id]
    
    while queue:
        current_msg_id = queue.pop(0)
        if current_msg_id in reachable_message_ids:
            continue
        
        reachable_message_ids.add(current_msg_id)
        
        for child_id in children_map.get(current_msg_id, []):
            if child_id not in reachable_message_ids and child_id in message_map:
                queue.append(child_id)

    # Identify orphans (messages not reachable from main_root)
    orphan_message_ids: Set[str] = set(message_map.keys()) - reachable_message_ids
    
    if not orphan_message_ids:
        ASCIIColors.info(f"Discussion {discussion.id} has no orphan messages.")
        return

    ASCIIColors.warning(f"Found {len(orphan_message_ids)} orphan messages in discussion {discussion.id}. Attempting to re-chain...")

    # Find orphan branch tops (highest message in each disconnected chain)
    # A message is an orphan branch top if it's an orphan, and its parent is NOT an orphan (or doesn't exist)
    orphan_branch_tops: List[LollmsMessage] = []
    
    for orphan_id in orphan_message_ids:
        msg = message_map[orphan_id]
        if msg.parent_id is None or msg.parent_id not in orphan_message_ids:
            orphan_branch_tops.append(msg)
            ASCIIColors.info(f"  - Identified orphan branch top: {orphan_id} (parent: {msg.parent_id})")

    # Sort orphan branch tops by creation time to process consistently
    orphan_branch_tops.sort(key=lambda m: m.created_at or datetime.datetime.min)

    # Re-parent orphan branch tops to the main root
    changes_made = False
    for orphan_top_msg in orphan_branch_tops:
        if orphan_top_msg.id == main_root_id: # Avoid re-parenting the main root to itself
            continue 
        
        # Check if it's already correctly parented but was missed by reachability initially
        if orphan_top_msg.parent_id == main_root_id:
             ASCIIColors.info(f"  - Orphan branch top {orphan_top_msg.id} is already parented to the main root. No re-parenting needed.")
             continue
             
        ASCIIColors.warning(f"  - Re-parenting orphan branch top {orphan_top_msg.id} (content: '{orphan_top_msg.content[:50]}...') to main root {main_root_id}.")
        discussion.update_message(orphan_top_msg.id, parent_id=main_root_id)
        changes_made = True

    if changes_made:
        discussion.commit()
        ASCIIColors.info(f"Orphan messages in discussion {discussion.id} re-chained. Discussion will be reloaded.")
    else:
        ASCIIColors.info(f"No re-chaining changes were actually made for discussion {discussion.id}.")


def get_user_discussion(username: str, discussion_id: str, create_if_missing: bool = False, lollms_client: Optional[LollmsClient] = None) -> Optional[LollmsDiscussion]:
    # If no client is passed, create one using the user's current settings.
    # This is the key change to ensure the correct context size and model are always used.
    lc = lollms_client if lollms_client is not None else get_user_lollms_client(username)
    dm = get_user_discussion_manager(username)
    
    # Extract max_context_size from the definitive LollmsClient instance (lc).
    max_context_size = user_sessions[username].get("llm_params",{}).get("ctx_size",None) or lc.get_ctx_size() or 4096
    
    discussion = dm.get_discussion(
        lollms_client=lc,
        discussion_id=discussion_id,
        max_context_size=max_context_size,
        autosave=True
    )
    
    if discussion:
        discussion.lollms_client = lc
        discussion.max_context_size = max_context_size  # Ensure it's correctly set on existing discussions

        # --- NEW: Call fix_lollms_discussion_orphans after loading ---
        fix_lollms_discussion_orphans(discussion)
        # Re-fetch the discussion after fixing, to ensure its internal graph is updated
        # This is crucial because fix_lollms_discussion_orphans modifies the DB directly via discussion.update_message
        # and then commits. The in-memory LollmsDiscussion object might not reflect these changes immediately.
        discussion = dm.get_discussion(
            lollms_client=lc,
            discussion_id=discussion_id,
            max_context_size=max_context_size,
            autosave=True # Important to ensure all changes are saved
        )
        if discussion is None: # Discussion might have been corrupted or deleted by the fix if main_root_id was faulty etc.
            ASCIIColors.error(f"Failed to reload discussion {discussion_id} after orphan fix. It might be corrupted.")
            return None
        # --- END NEW ---

        # --- FIX: In-place migration for legacy discussion_images format ---
        if discussion.metadata and 'discussion_images' in discussion.metadata:
            images_data = discussion.metadata['discussion_images']
            # Check if migration is needed (if it is a list, not a dict with 'data' key)
            if isinstance(images_data, list):
                print(f"INFO: Migrating legacy image format for discussion {discussion_id}")
                
                # Handle list of strings (oldest format) or list of dicts (intermediate format)
                image_list = []
                active_list = []
                for item in images_data:
                    if isinstance(item, dict) and 'image' in item:
                        image_list.append(item['image'])
                        active_list.append(item.get('active', True))
                    elif isinstance(item, str):
                        image_list.append(item)
                        active_list.append(True)

                new_images_format = {
                    'data': image_list,
                    'active': active_list
                }
                discussion.set_metadata_item('discussion_images', new_images_format)
                # The object in memory now has the old format. We need to update it.
                discussion.images = new_images_format['data']
                discussion.active_images = new_images_format['active']
        return discussion
    elif create_if_missing:
        new_discussion = LollmsDiscussion.create_new(
            lollms_client=lc,
            db_manager=dm,
            id=discussion_id,
            max_context_size=max_context_size,
            autosave=True,
            discussion_metadata={"title": f"New Discussion {discussion_id[:8]}"},
        )
        return new_discussion
    return None