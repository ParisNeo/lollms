# backend/tasks/discussion_tasks.py
import shutil
import json
import re
from datetime import datetime
from typing import Any, Dict, Optional

from ascii_colors import trace_exception, ASCIIColors

from backend.db.models.user import User as DBUser, UserMessageGrade, UserStarredDiscussion
from backend.db.models.memory import UserMemory
from backend.discussion import get_user_discussion, get_user_discussion_manager
from backend.session import get_user_discussion_assets_path, get_user_lollms_client
from backend.task_manager import Task
from backend.ws_manager import manager

def _process_data_zone_task(task: Task, username: str, discussion_id: str, contextual_prompt: Optional[str]):
    task.log("Starting data zone processing task...")
    discussion = get_user_discussion(username, discussion_id)
    if not discussion:
        raise ValueError("Discussion not found.")
    
    with task.db_session_factory() as db:
        db_user = db.query(DBUser).filter(DBUser.username == username).first()
        if not db_user:
            raise Exception(f"User '{username}' not found.")
        
        user_data_zone = db_user.data_zone or ""
        now = datetime.now()
        replacements = {
            "{{date}}": now.strftime("%Y-%m-%d"),
            "{{time}}": now.strftime("%H:%M:%S"),
            "{{datetime}}": now.strftime("%Y-%m-%d %H:%M:%S"),
            "{{user_name}}": username,
        }
        processed_user_data_zone = user_data_zone
        for placeholder, value in replacements.items():
            processed_user_data_zone = processed_user_data_zone.replace(placeholder, value)
    
    all_images_info = discussion.get_discussion_images()
    
    if (not discussion.discussion_data_zone or not discussion.discussion_data_zone.strip()) and not all_images_info and (not contextual_prompt or not contextual_prompt.strip()):
        task.log("Data zone and prompt are empty, nothing to process.", "WARNING")
        return {"discussion_id": discussion_id, "new_content": ""}
    
    def summary_callback(message: str, msg_type: Any, params: Optional[Dict] = None):
        """Callback to update the task in real-time."""
        if task.cancellation_event.is_set():
            task.log("Cancellation requested, stopping generation.", level="WARNING")
            return False
        task.log(message)
        task.set_description(message)
        if params and 'progress' in params:
            task.set_progress(int(params['progress']))
        return True

    prompt_to_use = contextual_prompt
    if (not discussion.discussion_data_zone or not discussion.discussion_data_zone.strip()) and not prompt_to_use and all_images_info:
        prompt_to_use = "Describe the attached image(s) in detail."
        task.log(f"No text found. Using default prompt: '{prompt_to_use}'")

    discussion_images_b64 = [img_info['data'] for img_info in all_images_info if img_info.get('active', True)]
    lc = get_user_lollms_client(username)
    
    summary = lc.long_context_processing(
        text_to_process = discussion.discussion_data_zone,
        images=discussion_images_b64,
        contextual_prompt=prompt_to_use,
        system_prompt=processed_user_data_zone,
        context_fill_percentage = 1,
        overlap_tokens= 0,
        expected_generation_tokens = int(lc.llm.default_ctx_size/6),
        max_scratchpad_tokens = int(lc.llm.default_ctx_size/4),
        scratchpad_compression_threshold = int(60*lc.llm.default_ctx_size/64),
        streaming_callback=summary_callback
    )
    
    if isinstance(summary, dict) and 'error' in summary:
        error_message = f"Failed to process data zone: {summary['error']}"
        task.log(error_message, "ERROR")
        raise Exception(error_message)

    if not isinstance(summary, str):
        task.log(f"Unexpected non-string result from processing: {type(summary)}. Converting to string.", "WARNING")
        summary = str(summary)
        
    discussion.discussion_data_zone = summary
    discussion.loaded_artefacts = [] # Unload all artefacts after processing
    discussion.commit()
    
    all_images_info = discussion.get_discussion_images()
    task.set_progress(100)
    task.set_description("Processing complete and saved.")
    
    return {
        "discussion_id": discussion_id, 
        "new_content": summary, 
        "zone": "discussion",
        "discussion_images": [img_info['data'] for img_info in all_images_info],
        "active_discussion_images": [img_info['active'] for img_info in all_images_info]
    }

def _memorize_ltm_task(task: Task, username: str, discussion_id: str):
    task.log("Starting long-term memory memorization task...")
    try:
        with task.db_session_factory() as db:
            db_user = db.query(DBUser).filter(DBUser.username == username).first()
            if not db_user:
                raise Exception("User not found.")
            
            discussion = get_user_discussion(username, discussion_id)
            if not discussion:
                raise ValueError("Discussion not found.")
            
            # Explicitly load messages
            task.set_progress(10)
            task.log("Loading discussion history...")
            if hasattr(discussion, 'load_messages'):
                discussion.load_messages()
            messages = discussion.messages
            if not messages:
                task.log("No messages in discussion to memorize.", "WARNING")
                return {"discussion_id": discussion_id, "zone": "memory"}

            # Format conversation for LLM
            conversation_text = ""
            for msg in messages:
                sender = msg.sender or "Unknown"
                content = msg.content or ""
                conversation_text += f"{sender}: {content}\n\n"

            task.set_progress(30)
            task.log("Analyzing conversation for important facts...")
            
            lc = get_user_lollms_client(username)
            
            system_prompt = """You are a Memory Assistant. Your goal is to extract important, long-term information about the user from the provided conversation.
Identify key facts such as names, preferences, relationships, specific work details, or important events.
Ignore casual conversation, greetings, or temporary context.
If no important information is found, return {"memories": []}.
"""
            template = """{
  "memories": [
    {"title": "Title of the memory", "content": "Content of the memory"}
  ]
}"""
            # Truncate conversation if too long (simple heuristic)
            max_chars = 12000 
            if len(conversation_text) > max_chars:
                conversation_text = conversation_text[-max_chars:]

            # Use generate_code to handle structure enforcement and thinking block removal
            code_content = lc.generate_code(
                conversation_text,
                system_prompt=system_prompt,
                template=template,
                language="json",
                n_predict=1024,
                temperature=0.1
            )
            
            task.set_progress(70)
            task.log("Parsing extracted memories...")
            
            if not code_content:
                task.log("AI failed to generate memory structure.", "WARNING")
                return {"discussion_id": discussion_id, "zone": "memory"}

            try:
                # Clean any potential leading/trailing whitespace before parsing
                data = json.loads(code_content.strip())
                extracted_memories = data.get("memories", [])
            except json.JSONDecodeError as e:
                task.log(f"Failed to parse JSON from AI response: {e}. Content: {code_content[:100]}...", "ERROR")
                extracted_memories = []

            count = 0
            if extracted_memories:
                for mem in extracted_memories:
                    title = mem.get("title")
                    content = mem.get("content")
                    if title and content:
                        new_memory = UserMemory(
                            title=title,
                            content=content,
                            owner_user_id=db_user.id
                        )
                        db.add(new_memory)
                        count += 1
                        task.log(f"Extracted: {title}")
                
                if count > 0:
                    db.commit()
                    task.log(f"Successfully saved {count} new memories.")
                    
                    # Push notification manually to ensure immediate UI update via WS
                    from backend.ws_manager import manager
                    manager.send_personal_message_sync({
                        "type": "data_zone_processed",
                        "data": {"discussion_id": discussion_id, "zone": "memory"}
                    }, db_user.id)
                else:
                    task.log("No valid memory objects found in response.", "INFO")
            else:
                task.log("No important memories found in this conversation.", "INFO")
    
        task.set_progress(100)
        task.log("Memorization task finished.")
        return {"discussion_id": discussion_id, "zone": "memory"}

    except Exception as e:
        task.log(f"Memorization failed: {str(e)}", "ERROR")
        trace_exception(e)
        raise e


def _prune_empty_discussions_task(task: Task, username: str):
    task.log("Starting prune of empty and single-message discussions.")
    dm = get_user_discussion_manager(username)
    all_discs_infos = dm.list_discussions()
    total_discussions = len(all_discs_infos)
    discussions_to_delete = []

    task.log(f"Scanning {total_discussions} discussions for user '{username}'.")
    
    discussion_db_session = dm.get_session()
    try:
        for i, disc_info in enumerate(all_discs_infos):
            if task.cancellation_event.is_set():
                task.log("Scan for prunable discussions cancelled.", level="WARNING")
                break
            discussion_id = disc_info['id']
            try:
                message_count = discussion_db_session.query(dm.MessageModel).filter(dm.MessageModel.discussion_id == discussion_id).count()
                if message_count <= 1:
                    discussions_to_delete.append(discussion_id)
            except Exception as e:
                task.log(f"Could not process discussion {discussion_id} for pruning: {e}", level="WARNING")
            
            progress = int(50 * (i + 1) / total_discussions) if total_discussions > 0 else 50
            task.set_progress(progress)
    finally:
        discussion_db_session.close()

    if task.cancellation_event.is_set():
        return {"message": "Pruning task cancelled during scan.", "deleted_count": 0}

    if not discussions_to_delete:
        task.log("No empty discussions found to prune.")
        task.set_progress(100)
        return {"message": "Pruning complete. No empty discussions found.", "deleted_count": 0}

    task.log(f"Found {len(discussions_to_delete)} discussions to delete. Starting deletion process...")
    task.set_progress(50)
    deleted_count = 0
    failed_count = 0
    
    with task.db_session_factory() as db:
        try:
            db_user = db.query(DBUser).filter(DBUser.username == username).one()
            
            for discussion_id in discussions_to_delete:
                if task.cancellation_event.is_set():
                    break

                try:
                    dm.delete_discussion(discussion_id)
                    assets_path = get_user_discussion_assets_path(username) / discussion_id
                    if assets_path.exists() and assets_path.is_dir():
                        shutil.rmtree(assets_path, ignore_errors=True)
                    
                    db.query(UserStarredDiscussion).filter_by(user_id=db_user.id, discussion_id=discussion_id).delete(synchronize_session=False)
                    db.query(UserMessageGrade).filter_by(user_id=db_user.id, discussion_id=discussion_id).delete(synchronize_session=False)

                    deleted_count += 1
                except Exception as e:
                    print(f"ERROR: Failed to delete discussion {discussion_id} during prune: {e}")
                    failed_count += 1
            
            db.commit()

            task.set_progress(100)
            
            if deleted_count > 0:
                task.log(f"Successfully pruned {deleted_count} discussions.")
            if failed_count > 0:
                task.log(f"Failed to prune {failed_count} discussions. Check server console for details.", level="ERROR")
            if task.cancellation_event.is_set():
                task.log(f"Pruning cancelled after deleting {deleted_count} discussions.", level="WARNING")

            return {"message": f"Pruning complete. Deleted: {deleted_count}, Failed: {failed_count}.", "deleted_count": deleted_count, "failed_count": failed_count}
        except Exception as e:
            db.rollback()
            task.log(f"A critical database error occurred during the commit phase: {e}", level="CRITICAL")
            raise e
