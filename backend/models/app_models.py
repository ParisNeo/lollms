# backend/models/app_models.py
import uuid
import yaml
from pathlib import Path
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass, field as dataclass_field

# Forward declaration or import if LollmsClient is also refactored
# from lollms_client import LollmsClient, ELF_COMPLETION_FORMAT 
# For now, assume LollmsClient is available globally or adjust import
from lollms_client import LollmsClient, LollmsDiscussion as LollmsClientDiscussion, ELF_COMPLETION_FORMAT

from backend.config import LOLLMS_CLIENT_DEFAULTS # For ctx_size default


@dataclass
class AppLollmsMessage:
    sender: str
    content: str
    id: str = dataclass_field(default_factory=lambda: str(uuid.uuid4()))
    parent_message_id: Optional[str] = None
    binding_name: Optional[str] = None
    model_name: Optional[str] = None
    token_count: Optional[int] = None
    image_references: Optional[List[str]] = dataclass_field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            k: v for k, v in self.__dict__.items() if v is not None and k != "image_references"
        } | {"image_references": self.image_references or []}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppLollmsMessage":
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


class AppLollmsDiscussion:
    def __init__(self, lollms_client_instance: LollmsClient, discussion_id: Optional[str] = None, title: Optional[str] = None):
        self.messages: List[AppLollmsMessage] = []
        self.lollms_client: LollmsClient = lollms_client_instance
        self.discussion_id: str = discussion_id or str(uuid.uuid4())
        raw_title = title or f"New Discussion {self.discussion_id[:8]}"
        self.title: str = (raw_title[:250] + "...") if len(raw_title) > 253 else raw_title
        self.rag_datastore_id: Optional[str] = None

    def add_message(
        self,
        sender: str,
        content: str,
        parent_message_id: Optional[str] = None,
        binding_name: Optional[str] = None,
        model_name: Optional[str] = None,
        token_count: Optional[int] = None,
        image_references: Optional[List[str]] = None
    ) -> AppLollmsMessage:
        message = AppLollmsMessage(
            sender=sender,
            content=content,
            parent_message_id=parent_message_id,
            binding_name=binding_name,
            model_name=model_name,
            token_count=token_count,
            image_references=image_references or []
        )
        self.messages.append(message)
        return message

    def edit_message(self, message_id: str, new_content: str) -> bool:
        for msg in self.messages:
            if msg.id == message_id:
                msg.content = new_content
                if msg.sender.lower() != self.lollms_client.user_name.lower(): # type: ignore
                    try:
                        msg.token_count = self.lollms_client.binding.count_tokens(new_content) # type: ignore
                    except Exception:
                        msg.token_count = len(new_content) // 3
                return True
        return False

    def delete_message(self, message_id: str) -> bool:
        original_len = len(self.messages)
        self.messages = [msg for msg in self.messages if msg.id != message_id]
        return len(self.messages) < original_len

    def _generate_title_from_messages_if_needed(self) -> None:
        is_generic_title = (
            self.title.startswith("New Discussion") or
            self.title.startswith("Imported") or
            self.title.startswith("Discussion ") or
            self.title.startswith("Sent: ") or
            not self.title.strip()
        )
        if is_generic_title and self.messages:
            first_user_message = next((m for m in self.messages if m.sender.lower() == self.lollms_client.user_name.lower()), None) # type: ignore
            if first_user_message:
                content_to_use = first_user_message.content
                if not content_to_use and first_user_message.image_references:
                    content_to_use = f"Image: {Path(first_user_message.image_references[0]).name}"
                if content_to_use:
                    new_title_base = content_to_use.strip().split("\n")[0]
                    max_title_len = 50
                    new_title = (new_title_base[: max_title_len - 3] + "...") if len(new_title_base) > max_title_len else new_title_base
                    if new_title:
                        self.title = new_title

    def to_dict(self) -> Dict[str, Any]:
        self._generate_title_from_messages_if_needed()
        return {
            "discussion_id": self.discussion_id,
            "title": self.title,
            "messages": [message.to_dict() for message in self.messages],
            "rag_datastore_id": self.rag_datastore_id
        }

    def save_to_disk(self, file_path: Union[str, Path]) -> None:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as file:
            yaml.dump(self.to_dict(), file, sort_keys=False, allow_unicode=True, Dumper=yaml.SafeDumper)

    @classmethod
    def load_from_disk(cls, lollms_client_instance: LollmsClient, file_path: Union[str, Path]) -> Optional["AppLollmsDiscussion"]:
        actual_path = Path(file_path)
        if not actual_path.exists():
            print(f"WARNING: Discussion file not found: {actual_path}")
            return None
        try:
            with open(actual_path, "r", encoding="utf-8") as file:
                data = yaml.safe_load(file)
        except Exception as e:
            print(f"ERROR: Could not load/parse discussion from {actual_path}: {e}")
            return None

        if not isinstance(data, dict): # Handle old list-based format
            disc_id_from_path = actual_path.stem
            discussion = cls(lollms_client_instance, discussion_id=disc_id_from_path, title=f"Imported {disc_id_from_path[:8]}")
            if isinstance(data, list):
                for msg_data in data:
                    if isinstance(msg_data, dict) and "sender" in msg_data and "content" in msg_data:
                        discussion.messages.append(AppLollmsMessage.from_dict(msg_data))
            discussion._generate_title_from_messages_if_needed()
            return discussion

        discussion_id = data.get("discussion_id", actual_path.stem)
        title = data.get("title", f"Imported {discussion_id[:8]}")
        discussion = cls(lollms_client_instance, discussion_id=discussion_id, title=title)
        discussion.rag_datastore_id = data.get("rag_datastore_id")
        
        loaded_messages_data = data.get("messages", [])
        if isinstance(loaded_messages_data, list):
            for msg_data in loaded_messages_data:
                if isinstance(msg_data, dict) and "sender" in msg_data and "content" in msg_data:
                    discussion.messages.append(AppLollmsMessage.from_dict(msg_data))
                else:
                    print(f"WARNING: Skipping malformed message data in {actual_path}: {msg_data}")
        
        if (not discussion.title or 
            discussion.title.startswith("Imported ") or 
            discussion.title.startswith("New Discussion ") or
            discussion.title.startswith("Sent: ")):
            discussion._generate_title_from_messages_if_needed()
        return discussion

    def prepare_query_for_llm(self, current_prompt_text: str, image_paths_for_llm: Optional[List[str]], max_total_tokens: Optional[int] = None) -> str:
        lc = self.lollms_client
        if max_total_tokens is None:
            max_total_tokens = getattr(lc, "ctx_size", LOLLMS_CLIENT_DEFAULTS.get("ctx_size", 4096)) # type: ignore
        
        client_discussion = LollmsClientDiscussion(lc) # type: ignore
        for app_msg in self.messages:
            client_discussion.add_message(sender=app_msg.sender, content=app_msg.content)
        
        user_prefix = f"{lc.separator_template}{lc.user_name}" # type: ignore
        ai_prefix = f"\n{lc.separator_template}{lc.ai_name}\n" # type: ignore
        
        current_turn_formatted_text_only = f"{user_prefix}\n{current_prompt_text}{ai_prefix}"
        try:
            current_turn_tokens = self.lollms_client.binding.count_tokens(current_turn_formatted_text_only) # type: ignore
        except Exception:
            current_turn_tokens = len(current_turn_formatted_text_only) // 3
        
        tokens_for_history = max_total_tokens - current_turn_tokens
        tokens_for_history = max(0, tokens_for_history)
        
        history_text = client_discussion.format_discussion(max_allowed_tokens=tokens_for_history)
        return f"{history_text}{user_prefix}\n{current_prompt_text}{ai_prefix}"