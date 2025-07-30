from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.db import get_db
from backend.db.models.prompt import SavedPrompt as DBSavedPrompt
from backend.db.models.dm import DirectMessage as DBDirectMessage
from backend.db.models.user import User as DBUser
from backend.models import UserAuthDetails, PromptCreate, PromptPublic, PromptUpdate, PromptShareRequest, PromptsExport, PromptsImport
from backend.session import get_current_active_user
from backend.ws_manager import manager

prompts_router = APIRouter(
    prefix="/api/prompts",
    tags=["Prompts"],
    dependencies=[Depends(get_current_active_user)]
)

@prompts_router.get("", response_model=List[PromptPublic])
def get_user_saved_prompts(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    prompts = db.query(DBSavedPrompt).filter(DBSavedPrompt.owner_user_id == current_user.id).order_by(DBSavedPrompt.name).all()
    return prompts

@prompts_router.post("", response_model=PromptPublic, status_code=status.HTTP_201_CREATED)
def create_saved_prompt(
    prompt_data: PromptCreate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    new_prompt = DBSavedPrompt(
        name=prompt_data.name,
        content=prompt_data.content,
        owner_user_id=current_user.id
    )
    db.add(new_prompt)
    db.commit()
    db.refresh(new_prompt)
    return new_prompt

@prompts_router.put("/{prompt_id}", response_model=PromptPublic)
def update_saved_prompt(
    prompt_id: str,
    prompt_data: PromptUpdate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    prompt_to_update = db.query(DBSavedPrompt).filter(DBSavedPrompt.id == prompt_id, DBSavedPrompt.owner_user_id == current_user.id).first()
    if not prompt_to_update:
        raise HTTPException(status_code=404, detail="Prompt not found.")
    
    update_data = prompt_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(prompt_to_update, key, value)
    
    db.commit()
    db.refresh(prompt_to_update)
    return prompt_to_update

@prompts_router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_prompt(
    prompt_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    prompt_to_delete = db.query(DBSavedPrompt).filter(DBSavedPrompt.id == prompt_id, DBSavedPrompt.owner_user_id == current_user.id).first()
    if not prompt_to_delete:
        raise HTTPException(status_code=404, detail="Prompt not found.")
    
    db.delete(prompt_to_delete)
    db.commit()
    return None

@prompts_router.post("/share", status_code=status.HTTP_200_OK)
async def share_prompt_as_dm(
    payload: PromptShareRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    receiver = db.query(DBUser).filter(DBUser.username == payload.target_username).first()
    if not receiver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receiver user not found.")

    if current_user.id == receiver.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot share a prompt with yourself.")
    
    formatted_content = f"--- SHARED PROMPT ---\n\n{payload.prompt_content}"

    new_message = DBDirectMessage(
        sender_id=current_user.id,
        receiver_id=receiver.id,
        content=formatted_content
    )
    db.add(new_message)
    db.commit()
    db.refresh(new_message, ['sender', 'receiver'])
    
    from backend.models.dm import DirectMessagePublic
    response_data = DirectMessagePublic(
        id=new_message.id, content=new_message.content, sender_id=new_message.sender_id,
        receiver_id=new_message.receiver_id, sent_at=new_message.sent_at, read_at=new_message.read_at,
        sender_username=new_message.sender.username, receiver_username=new_message.receiver.username
    )

    await manager.send_personal_message(message_data=response_data.model_dump(mode="json"), user_id=receiver.id)
    return {"message": f"Prompt successfully sent to {payload.target_username}."}

@prompts_router.get("/export", response_model=PromptsExport)
def export_user_prompts(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    prompts_db = db.query(DBSavedPrompt).filter(DBSavedPrompt.owner_user_id == current_user.id).all()
    prompts_to_export = [PromptBase(name=p.name, content=p.content) for p in prompts_db]
    return PromptsExport(prompts=prompts_to_export)

@prompts_router.post("/import", status_code=status.HTTP_201_CREATED)
def import_user_prompts(
    import_data: PromptsImport,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    imported_count = 0
    skipped_count = 0
    for prompt_data in import_data.prompts:
        existing = db.query(DBSavedPrompt).filter(
            DBSavedPrompt.owner_user_id == current_user.id,
            DBSavedPrompt.name == prompt_data.name
        ).first()
        
        if existing:
            skipped_count += 1
            continue

        new_prompt = DBSavedPrompt(
            name=prompt_data.name,
            content=prompt_data.content,
            owner_user_id=current_user.id
        )
        db.add(new_prompt)
        imported_count += 1
    
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="An integrity error occurred during import.")

    return {"message": f"Successfully imported {imported_count} prompts. Skipped {skipped_count} due to name conflicts."}