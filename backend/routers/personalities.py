# backend/routers/personalities.py

# Standard Library Imports
import traceback
from typing import List, Dict, Optional

# Third-Party Imports
from fastapi import (
    APIRouter, Depends, HTTPException
)
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, and_

# Local Application Imports
from backend.database_setup import (
    User as DBUser,
    Personality as DBPersonality,
    get_db,
)
from backend.models import (
    UserAuthDetails, PersonalityPublic, PersonalityCreate,
    PersonalityUpdate, PersonalitySendRequest
)
from backend.session import (
    get_current_active_user,
    get_current_db_user_from_token,
    user_sessions,
)

personalities_router = APIRouter(prefix="/api/personalities", tags=["Personalities"])

def get_personality_public_from_db(db_personality: DBPersonality, owner_username: Optional[str] = None) -> PersonalityPublic:
    if owner_username is None and db_personality.owner:
        owner_username = db_personality.owner.username
    
    return PersonalityPublic(
        id=db_personality.id,
        name=db_personality.name,
        category=db_personality.category,
        author=db_personality.author,
        description=db_personality.description,
        prompt_text=db_personality.prompt_text,
        disclaimer=db_personality.disclaimer,
        script_code=db_personality.script_code,
        icon_base64=db_personality.icon_base64,
        created_at=db_personality.created_at,
        updated_at=db_personality.updated_at,
        is_public=db_personality.is_public,
        owner_username=owner_username
    )

@personalities_router.post("", response_model=PersonalityPublic, status_code=201)
async def create_personality(personality_data: PersonalityCreate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> PersonalityPublic:
    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).one()
    
    existing_personality = db.query(DBPersonality).filter(
        DBPersonality.owner_user_id == db_user.id,
        DBPersonality.name == personality_data.name
    ).first()
    if existing_personality:
        raise HTTPException(status_code=400, detail=f"You already have a personality named '{personality_data.name}'.")

    if personality_data.is_public and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only administrators can create public personalities.")
    
    db_personality = DBPersonality(
        **personality_data.model_dump(exclude={"is_public"}),
        owner_user_id=db_user.id,
        is_public=personality_data.is_public if current_user.is_admin else False
    )

    try:
        db.add(db_personality)
        db.commit()
        db.refresh(db_personality)
        return get_personality_public_from_db(db_personality, current_user.username)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Personality name conflict (race condition).")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@personalities_router.get("/my", response_model=List[PersonalityPublic])
async def get_my_personalities(current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[PersonalityPublic]:
    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).one()
    
    owned_personalities_db = db.query(DBPersonality).filter(DBPersonality.owner_user_id == db_user.id).order_by(DBPersonality.name).all()
    return [get_personality_public_from_db(p, current_user.username) for p in owned_personalities_db]

@personalities_router.get("/public", response_model=List[PersonalityPublic])
async def get_public_personalities(db: Session = Depends(get_db)) -> List[PersonalityPublic]:
    public_personalities_db = db.query(DBPersonality).options(joinedload(DBPersonality.owner)).filter(DBPersonality.is_public == True).order_by(DBPersonality.category, DBPersonality.name).all()
    return [get_personality_public_from_db(p) for p in public_personalities_db]

@personalities_router.get("/{personality_id}", response_model=PersonalityPublic)
async def get_personality(personality_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> PersonalityPublic:
    db_personality = db.query(DBPersonality).options(joinedload(DBPersonality.owner)).filter(DBPersonality.id == personality_id).first()
    if not db_personality:
        raise HTTPException(status_code=404, detail="Personality not found.")

    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).one()
    is_owner = (db_personality.owner_user_id == db_user.id)

    if not db_personality.is_public and not is_owner:
        raise HTTPException(status_code=403, detail="You do not have permission to view this personality.")
    
    return get_personality_public_from_db(db_personality)

@personalities_router.put("/{personality_id}", response_model=PersonalityPublic)
async def update_personality(personality_id: str, personality_data: PersonalityUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> PersonalityPublic:
    db_personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
    if not db_personality:
        raise HTTPException(status_code=404, detail="Personality not found.")

    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).one()
    is_owner = (db_personality.owner_user_id == db_user.id)

    if not is_owner and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="You do not have permission to update this personality.")
    
    if personality_data.is_public is not None:
        if not current_user.is_admin:
            if is_owner and personality_data.is_public != db_personality.is_public:
                 raise HTTPException(status_code=403, detail="Only administrators can change the public status of a personality.")
        elif current_user.is_admin:
            db_personality.is_public = personality_data.is_public
    
    update_data = personality_data.model_dump(exclude_unset=True, exclude={"is_public"})

    if "name" in update_data and update_data["name"] != db_personality.name:
        owner_id_for_check = db_personality.owner_user_id
        q = db.query(DBPersonality).filter(
            DBPersonality.owner_user_id == owner_id_for_check,
            DBPersonality.name == update_data["name"],
            DBPersonality.id != personality_id
        )
        if q.first():
            raise HTTPException(status_code=400, detail=f"A personality named '{update_data['name']}' already exists.")

    for field, value in update_data.items():
        if hasattr(db_personality, field):
            setattr(db_personality, field, value)
    
    try:
        db.commit()
        db.refresh(db_personality, attribute_names=['owner']) 
        return get_personality_public_from_db(db_personality)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Personality name conflict (race condition).")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@personalities_router.delete("/{personality_id}", status_code=200)
async def delete_personality(personality_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    db_personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
    if not db_personality:
        raise HTTPException(status_code=404, detail="Personality not found.")

    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).one()
    is_owner = (db_personality.owner_user_id == db_user.id)

    if not is_owner and not (current_user.is_admin and (db_personality.is_public or db_personality.owner_user_id is None)):
        raise HTTPException(status_code=403, detail="You do not have permission to delete this personality.")

    users_with_this_active = db.query(DBUser).filter(DBUser.active_personality_id == personality_id).all()
    for user in users_with_this_active:
        user.active_personality_id = None
        if user.username in user_sessions:
            user_sessions[user.username]["active_personality_id"] = None
            user_sessions[user.username]["active_personality_prompt"] = None

    try:
        db.delete(db_personality)
        db.commit()
        return {"message": f"Personality '{db_personality.name}' deleted successfully."}
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@personalities_router.post("/{personality_id}/send", response_model=PersonalityPublic)
async def send_personality_to_user(personality_id: str, send_request: PersonalitySendRequest, current_db_user: DBUser = Depends(get_current_db_user_from_token), db: Session = Depends(get_db)) -> PersonalityPublic:
    q = db.query(DBPersonality).filter(
        DBPersonality.id == personality_id,
        or_(
            DBPersonality.owner_user_id == current_db_user.id,
            and_(DBPersonality.is_public == True, current_db_user.is_admin == True)
        )
    )
    original_personality = q.first()
    if not original_personality:
        raise HTTPException(status_code=404, detail="Personality not found or you don't have permission to send it.")

    target_user = db.query(DBUser).filter(DBUser.username == send_request.target_username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"Target user '{send_request.target_username}' not found.")
    
    if target_user.id == current_db_user.id:
        raise HTTPException(status_code=400, detail="Cannot send a personality to yourself.")

    existing_target_pers = db.query(DBPersonality).filter(
        DBPersonality.owner_user_id == target_user.id,
        DBPersonality.name == original_personality.name
    ).first()
    if existing_target_pers:
        raise HTTPException(status_code=400, detail=f"User '{target_user.username}' already has a personality named '{original_personality.name}'.")

    copied_personality = DBPersonality(
        name=original_personality.name,
        category=original_personality.category,
        author=f"Sent by {current_db_user.username}",
        description=original_personality.description,
        prompt_text=original_personality.prompt_text,
        disclaimer=original_personality.disclaimer,
        script_code=original_personality.script_code,
        icon_base64=original_personality.icon_base64,
        owner_user_id=target_user.id,
        is_public=False
    )
    db.add(copied_personality)
    try:
        db.commit()
        db.refresh(copied_personality)
        return get_personality_public_from_db(copied_personality, target_user.username)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Failed to send personality due to a name conflict for the target user.")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error sending personality: {str(e)}")