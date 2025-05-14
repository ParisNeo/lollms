# backend/routers/prompts.py
import uuid
from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from backend.models.api_models import (
    PromptCreate, PromptPublic, PromptUpdate, UserAuthDetails
)
from backend.database.setup import (
    User as DBUser, Prompt as DBPrompt, get_db
)
from backend.services.auth_service import get_current_active_user

prompts_router = APIRouter(prefix="/api/prompts", tags=["Prompts"])

@prompts_router.post("", response_model=PromptPublic, status_code=201)
async def create_prompt(
    prompt_data: PromptCreate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> PromptPublic:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: # Should be caught by auth
        raise HTTPException(status_code=404, detail="User not found.")

    # Check for existing prompt with the same name for this user
    if db.query(DBPrompt).filter_by(owner_user_id=user_db_record.id, name=prompt_data.name).first():
        raise HTTPException(status_code=400, detail=f"A prompt with the name '{prompt_data.name}' already exists for you.")

    new_db_prompt = DBPrompt(
        owner_user_id=user_db_record.id,
        **prompt_data.model_dump() # Unpack Pydantic model into DB model fields
    )
    try:
        db.add(new_db_prompt)
        db.commit()
        db.refresh(new_db_prompt)
        # model_validate needs context if owner_username is not directly on new_db_prompt
        return PromptPublic.model_validate(new_db_prompt, context={"owner_username": current_user.username})
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error creating prompt: {e}")


@prompts_router.get("/mine", response_model=List[PromptPublic])
async def get_my_prompts(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[PromptPublic]:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record:
        raise HTTPException(status_code=404, detail="User not found.")

    prompts_db = db.query(DBPrompt).filter(
        DBPrompt.owner_user_id == user_db_record.id
    ).order_by(DBPrompt.name).all()
    
    return [
        PromptPublic.model_validate(p, context={"owner_username": current_user.username})
        for p in prompts_db
    ]


@prompts_router.get("/store", response_model=List[PromptPublic])
async def get_public_prompts_store(
    current_user: UserAuthDetails = Depends(get_current_active_user), # Auth needed to personalize (e.g., sort own first)
    db: Session = Depends(get_db)
) -> List[PromptPublic]:
    # Eager load owner to get owner.username for the context
    # Sort to show current user's public prompts first, then by name
    prompts_db = db.query(DBPrompt).options(
        joinedload(DBPrompt.owner)
    ).filter(
        DBPrompt.is_public == True
    ).order_by(
        DBPrompt.owner.has(DBUser.username == current_user.username).desc(), # True (1) before False (0)
        DBPrompt.name
    ).all()
    
    return [
        PromptPublic.model_validate(p, context={"owner_username": p.owner.username})
        for p in prompts_db
    ]


@prompts_router.get("/{prompt_id}", response_model=PromptPublic)
async def get_prompt_details(
    prompt_id: int,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> PromptPublic:
    prompt_db = db.query(DBPrompt).options(
        joinedload(DBPrompt.owner) # Eager load owner
    ).filter(DBPrompt.id == prompt_id).first()

    if not prompt_db:
        raise HTTPException(status_code=404, detail="Prompt not found.")

    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: # Should not happen
        raise HTTPException(status_code=404, detail="Current user not found in DB.") 
        
    # Check access: user must be owner OR prompt must be public
    if prompt_db.owner_user_id != user_db_record.id and not prompt_db.is_public:
        raise HTTPException(status_code=403, detail="Access denied. This prompt is not public and you are not the owner.")
        
    return PromptPublic.model_validate(prompt_db, context={"owner_username": prompt_db.owner.username})


@prompts_router.put("/{prompt_id}", response_model=PromptPublic)
async def update_prompt(
    prompt_id: int,
    prompt_data: PromptUpdate, # Contains all fields, any can be updated
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> PromptPublic:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record:
        raise HTTPException(status_code=404, detail="User not found.")

    prompt_db = db.query(DBPrompt).filter(
        DBPrompt.id == prompt_id,
        DBPrompt.owner_user_id == user_db_record.id # Can only update own prompts
    ).first()

    if not prompt_db:
        raise HTTPException(status_code=404, detail="Prompt not found or you are not the owner.")

    # Check for name conflict if name is being changed
    if prompt_data.name != prompt_db.name:
        if db.query(DBPrompt).filter(
            DBPrompt.owner_user_id == user_db_record.id,
            DBPrompt.name == prompt_data.name,
            DBPrompt.id != prompt_id # Exclude current prompt from check
        ).first():
            raise HTTPException(status_code=400, detail=f"Another prompt with the name '{prompt_data.name}' already exists for you.")

    # Update fields from prompt_data
    for field, value in prompt_data.model_dump(exclude_unset=True).items(): # exclude_unset to only update provided fields
        setattr(prompt_db, field, value)
    
    try:
        db.commit()
        db.refresh(prompt_db)
        return PromptPublic.model_validate(prompt_db, context={"owner_username": current_user.username})
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error updating prompt: {e}")


@prompts_router.delete("/{prompt_id}", status_code=200)
async def delete_prompt(
    prompt_id: int,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record:
        raise HTTPException(status_code=404, detail="User not found.")

    prompt_db = db.query(DBPrompt).filter(
        DBPrompt.id == prompt_id,
        DBPrompt.owner_user_id == user_db_record.id # Can only delete own prompts
    ).first()

    if not prompt_db:
        raise HTTPException(status_code=404, detail="Prompt not found or you are not the owner.")
    
    prompt_name_for_message = prompt_db.name
    try:
        db.delete(prompt_db)
        db.commit()
        return {"message": f"Prompt '{prompt_name_for_message}' deleted successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error deleting prompt: {e}")


@prompts_router.post("/{prompt_id}/add_to_my_prompts", response_model=PromptPublic, status_code=201)
async def copy_public_prompt_to_mine(
    prompt_id: int, # ID of the public prompt to copy
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> PromptPublic:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record:
        raise HTTPException(status_code=404, detail="User not found.")

    # Find the public prompt to copy
    public_prompt_to_copy = db.query(DBPrompt).filter(
        DBPrompt.id == prompt_id,
        DBPrompt.is_public == True
    ).first()

    if not public_prompt_to_copy:
        raise HTTPException(status_code=404, detail="Public prompt to copy not found or is not public.")
    
    if public_prompt_to_copy.owner_user_id == user_db_record.id:
        raise HTTPException(status_code=400, detail="Cannot copy your own prompt to your prompts this way.")

    # Handle potential name conflicts for the copied prompt
    new_copied_prompt_name = public_prompt_to_copy.name
    name_conflict_check = db.query(DBPrompt).filter_by(
        owner_user_id=user_db_record.id, name=new_copied_prompt_name
    ).first()
    
    if name_conflict_check: # If name exists, append a suffix
        new_copied_prompt_name = f"{public_prompt_to_copy.name} (Copied)"
        # Further check if "(Copied)" version also exists
        if db.query(DBPrompt).filter_by(owner_user_id=user_db_record.id, name=new_copied_prompt_name).first():
            new_copied_prompt_name = f"{public_prompt_to_copy.name} (Copied {uuid.uuid4().hex[:4]})" # Add unique hash

    # Create a new prompt for the current user based on the public one
    copied_prompt_db_obj = DBPrompt(
        owner_user_id=user_db_record.id,
        name=new_copied_prompt_name,
        category=public_prompt_to_copy.category,
        description=f"Copied from a public prompt. Original description: {public_prompt_to_copy.description or ''}",
        content=public_prompt_to_copy.content,
        is_public=False # Copied prompts are private by default for the new owner
    )
    
    try:
        db.add(copied_prompt_db_obj)
        db.commit()
        db.refresh(copied_prompt_db_obj)
        return PromptPublic.model_validate(copied_prompt_db_obj, context={"owner_username": current_user.username})
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error copying prompt: {e}")
