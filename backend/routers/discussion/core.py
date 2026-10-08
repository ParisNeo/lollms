# Standard Library Imports
import uuid
from typing import Dict, List, Optional, Any, Tuple

# Third-Party Imports
from fastapi import (
    APIRouter, Depends, HTTPException)
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ascii_colors import ASCIIColors, trace_exception

# Local Application Imports
from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.discussion import get_user_discussion
from backend.discussion_manager import get_user_discussion_manager
from backend.models import (UserAuthDetails, DiscussionTitleUpdate)
from backend.session import get_current_active_user, get_user_lollms_client
from backend.task_manager import task_manager
from backend.routers.discussion.helpers import get_discussion_and_owner_for_request

from lollms_client import LollmsDiscussion, LollmsDataManager, LollmsClient


def build_core_router(router: APIRouter):
    # --- New Discussion ---
    class CreateDiscussionRequest(BaseModel):
        title: Optional[str] = "Untitled"
        group_id: Optional[str] = None

    @router.post("/new", status_code=201)
    async def create_new_discussion(
        payload: CreateDiscussionRequest,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        try:
            lc = get_user_lollms_client(current_user.username)
            if not lc:
                raise HTTPException(status_code=503, detail="LLM service not available.")

            dm: LollmsDataManager = get_user_discussion_manager(current_user.username)
            if dm is None:
                raise HTTPException(status_code=500, detail="Failed to create a discussion manager.")

            title = str(payload.title or "Untitled")
            new_discussion_id = str(uuid.uuid4())

            discussion_obj: LollmsDiscussion = LollmsDiscussion.create_new(
                lollms_client=lc,
                db_manager=dm,
                id=new_discussion_id,
                discussion_metadata={"title": title}
            )

            if discussion_obj is None:
                raise HTTPException(status_code=500, detail="Failed to create discussion object.")

            db_discussion = discussion_obj.discussion
            db_discussion.title = title

            new_branch_id = discussion_obj.get_current_branch_id()

            return {
                "id": db_discussion.id,
                "title": db_discussion.title,
                "is_starred": False,
                "discussion_id": db_discussion.id,
                "current_branch_id": new_branch_id,
                "discussion_data_zone": db_discussion.discussion_data_zone,
                "active_personality_id": db_discussion.active_personality_id,
                "active_brain_id": db_discussion.active_brain_id,
                "llm_binding_name": db_discussion.llm_binding_name,
                "llm_model_name": db_discussion.llm_model_name,
            }
        except HTTPException:
            raise
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to create new discussion: {e}")

    @router.patch("/{discussion_id}", response_model=dict)
    async def update_discussion(
        discussion_id: str,
        title_update: DiscussionTitleUpdate,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion_obj, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'owner')
        if discussion_obj is None:
            raise HTTPException(status_code=404, detail="Discussion not found.")
        db_discussion = discussion_obj.discussion
        db_discussion.title = title_update.title
        discussion_obj.commit()
        return {"message": f"Discussion title updated successfully."}

    @router.get("/{discussion_id}", response_model=Dict[str, Any])
    async def get_discussion(
        discussion_id: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion_obj, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        if discussion_obj is None:
            raise HTTPException(status_code=404, detail="Discussion not found.")

        discussion_db = discussion_obj.discussion

        if discussion_db.discussion_metadata is None:
            discussion_db.discussion_metadata = {}

        active_tasks = [
            t.to_dict() for t in task_manager.tasks
            if t.discussion_id == discussion_db.id and t.status in ['pending', 'running'] and not t.cancellation_requested
        ]

        generation_status = discussion_db.generation_status
        is_active_generation = False
        if isinstance(generation_status, dict):
            is_active_generation = generation_status.get('status', 0) == 1

        return {
            "discussion_id": discussion_db.id,
            "title": discussion_db.title,
            "current_branch_id": discussion_obj.get_current_branch_id(),
            "discussion_data_zone": discussion_db.discussion_data_zone,
            "discussion_metadata": discussion_db.discussion_metadata,
            "active_personality_id": discussion_db.active_personality_id,
            "active_brain_id": discussion_db.active_brain_id,
            "llm_binding_name": discussion_db.llm_binding_name,
            "llm_model_name": discussion_db.llm_model_name,
            "is_shared_with_default_scopes": any(
                dm.group_scopes.is_default_scope
                for dm in discussion_db.group_memberships
                if hasattr(dm.group_scopes, 'is_default_scope')
            ),
            "active_tasks": active_tasks,
            "is_active_generation": is_active_generation
        }

    @router.get("/{discussion_id}/export_markdown", status_code=200)
    async def export_discussion_markdown(
        discussion_id: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """
        Exports the current active branch of the discussion as a Markdown string.
        """
        discussion_obj, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        if discussion_obj is None:
            raise HTTPException(status_code=404, detail="Discussion not found.")
        markdown_content = discussion_obj.export_discussion_as_markdown()

        return {"markdown": markdown_content}

    @router.get("/{discussion_id}/export_latex", status_code=200)
    async def export_discussion_latex(
        discussion_id: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        """
        Exports the current active branch of the discussion as a LaTeX string.
        """
        discussion_obj, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db)
        if discussion_obj is None:
            raise HTTPException(status_code=404, detail="Discussion not found.")
        latex_content = discussion_obj.export_discussion_as_latex()

        return {"latex": latex_content}

    @router.post("/{discussion_id}/switch_branch/{branch_id}")
    async def switch_branch(
        discussion_id: str,
        branch_id: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion_obj, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'interact')
        if discussion_obj is None:
            raise HTTPException(status_code=404, detail="Discussion not found.")
        discussion_obj.switch_to_branch(branch_id)
        discussion_obj.commit()
        return {"message": "Switched branch successfully"}

    @router.delete("/{discussion_id}", status_code=200)
    async def delete_discussion_endpoint(
        discussion_id: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        discussion_obj, _, _, _ = await get_discussion_and_owner_for_request(discussion_id, current_user, db, 'owner')
        if discussion_obj is None:
            raise HTTPException(status_code=404, detail="Discussion not found.")
        try:
            discussion_obj.delete_discussion()
            return {"message": f"Discussion deleted successfully."}
        except HTTPException:
            raise
        except Exception as e:
            trace_exception(e)
            raise HTTPException(status_code=500, detail=f"Failed to delete discussion: {e}")

    @router.post("/{discussion_id}/fork_compress", status_code=201)
    async def fork_and_compress_discussion(
        discussion_id: str,
        current_user: UserAuthDetails = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        ASCIIColors.info(f"Fork & Compress requested for discussion {discussion_id} by {current_user.username}")

        source_discussion_obj, _, _, _ = await get_discussion_and_owner_for_request(
            discussion_id, current_user, db, 'owner'
        )
        if source_discussion_obj is None:
            raise HTTPException(status_code=404, detail="Source discussion not found.")

        messages = source_discussion_obj.get_all_messages_flat()
        if not messages or len(messages) < 2:
            raise HTTPException(status_code=400, detail="Not enough content to compress")

        transcript_lines = []
        for msg in messages:
            sender = "User" if msg.sender_type == "user" else "Assistant"
            content = msg.content[:5000] if msg.content else ""
            transcript_lines.append(f"{sender}: {content}")

        full_transcript = "\n\n".join(transcript_lines)
        if len(full_transcript) > 100000:
            full_transcript = full_transcript[:100000] + "\n\n[... content truncated ...]"

        compression_prompt = (
            "You are an expert conversation summarizer. Compress the following discussion "
            "into a comprehensive summary that will serve as context for continuing the work.\n\n"
            "INSTRUCTIONS:\n"
            "- Summarize key topics, decisions, and completed work\n"
            "- Preserve technical details, file names, and specific requirements\n"
            "- Note pending tasks and next steps\n"
            "- Write in first person from the user's perspective\n\n"
            "DISCUSSION TRANSCRIPT:\n"
            f"{full_transcript}\n\n"
            "COMPRESSED SUMMARY (as a message from the user):"
        )

        lc = get_user_lollms_client(current_user.username)
        if not lc:
            raise HTTPException(status_code=503, detail="LLM service not available for this user.")

        summary_response: str = lc.generate_text(
            compression_prompt,
            max_new_tokens=2000,
            temperature=0.3
        )

        if not summary_response or not summary_response.strip():
            raise HTTPException(status_code=500, detail="Failed to generate summary")

        summary_content: str = summary_response.strip()

        source_discussion = source_discussion_obj
        source_title = (source_discussion.metadata or {}).get('title', getattr(source_discussion, 'title', ''))
        new_title = f"[Compressed] {source_title}" if source_title else "Compressed Discussion"

        dm: LollmsDataManager = get_user_discussion_manager(current_user.username)
        if dm is None:
            raise HTTPException(status_code=500, detail="Failed to create a discussion manager.")

        new_discussion_id = str(uuid.uuid4())

        new_discussion_obj: Optional[LollmsDiscussion] = LollmsDiscussion.create_new(
            lollms_client=lc,
            db_manager=dm,
            id=new_discussion_id,
            discussion_metadata={"title": new_title}
        )

        if new_discussion_obj is None:
            raise HTTPException(status_code=500, detail="Failed to create new discussion for fork.")

        db_discussion = new_discussion_obj
    
        # Safely copy attributes that may not exist on the DB object
        config_attrs = [
            'discussion_data_zone',
            'active_personality_id',
            'active_brain_id',
            'llm_binding_name',
            'llm_model_name',
            'tti_binding_name',
            'tti_model_name',
            'active_skills'
        ]
    
        for attr in config_attrs:
            try:
                source_val = getattr(source_discussion, attr, None)
                target_val = getattr(db_discussion, attr, None)
                if source_val is not None and target_val is not None:
                    setattr(db_discussion, attr, source_val)
            except Exception:
                # Attribute does not exist on the DB object, skip it
                pass

        # Copy metadata dictionary safely
        try:
            source_meta = source_discussion.metadata or {}
            target_meta = db_discussion.metadata or {}
            if isinstance(target_meta, dict) and isinstance(source_meta, dict):
                target_meta.update(source_meta)
        except Exception:
            pass

        # Set title via metadata (the reliable way based on previous fix)
        try:
            if hasattr(db_discussion, 'set_metadata_item'):
                db_discussion.set_metadata_item('title', new_title)
        except Exception:
            pass

        user_msg = new_discussion_obj.add_message(
            sender=current_user.username,
            content=summary_content,
            sender_type="user"
        )

        if user_msg is None:
            raise HTTPException(status_code=500, detail="Failed to add summary message to new discussion.")

        acknowledgment_content = (
            "I acknowledge receipt of the summarized context. I understand the work done so far "
            "and I'm ready to continue from this compressed state.\n\n"
            "Key points registered:\n"
            "- The summary above captures our previous discussion\n"
            "- All relevant artefacts and data zones have been preserved\n"
            "- Context is now optimized for efficient continuation\n\n"
            "How would you like to proceed?"
        )

        active_personality_id = getattr(source_discussion, 'active_personality_id', None)
        assistant_sender = f"Personality {active_personality_id}" if active_personality_id else "assistant"

        new_discussion_obj.add_message(
            sender=assistant_sender,
            content=acknowledgment_content,
            parent_id=user_msg.id,
            sender_type="assistant"
        )

        new_discussion_obj.commit()

        ASCIIColors.success(f"Created compressed fork {new_discussion_obj.id} from {discussion_id}")

        return {
            "id": new_discussion_obj.id,
            "title": new_title,
            "message": "Discussion forked and compressed successfully"
        }