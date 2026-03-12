import re
import yaml
import xml.etree.ElementTree as ET
from typing import List, Optional
import datetime

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel

from backend.db import get_db
from backend.db.models.skill import Skill as DBSkill
from backend.db.models.user import User as DBUser
from backend.models.user import UserAuthDetails
from backend.session import get_current_active_user
from backend.models.personality import PersonalitySendRequest

skills_router = APIRouter(
    prefix="/api/skills",
    tags=["Skills"],
    dependencies=[Depends(get_current_active_user)]
)

class SkillBase(BaseModel):
    name: str
    content: str
    description: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = "markdown"

class SkillCreate(SkillBase):
    pass

class SkillUpdate(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None

class SkillPublic(SkillBase):
    id: str
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True

@skills_router.get("", response_model=List[SkillPublic])
def get_skills(current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    skills = db.query(DBSkill).filter(DBSkill.owner_user_id == current_user.id).order_by(DBSkill.name).all()
    return skills

@skills_router.post("", response_model=SkillPublic, status_code=status.HTTP_201_CREATED)
def create_skill(skill: SkillCreate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    new_skill = DBSkill(**skill.model_dump(), owner_user_id=current_user.id)
    db.add(new_skill)
    try:
        db.commit()
        db.refresh(new_skill)
        return new_skill
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error creating skill.")

@skills_router.put("/{skill_id}", response_model=SkillPublic)
def update_skill(skill_id: str, skill_update: SkillUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    skill = db.query(DBSkill).filter(DBSkill.id == skill_id, DBSkill.owner_user_id == current_user.id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    update_data = skill_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(skill, key, value)
    
    try:
        db.commit()
        db.refresh(skill)
        return skill
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error updating skill.")

@skills_router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(skill_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    skill = db.query(DBSkill).filter(DBSkill.id == skill_id, DBSkill.owner_user_id == current_user.id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    db.delete(skill)
    db.commit()

class ExportFormat(BaseModel):
    format: str

@skills_router.post("/{skill_id}/export")
def export_skill(skill_id: str, payload: ExportFormat, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    skill = db.query(DBSkill).filter(DBSkill.id == skill_id, DBSkill.owner_user_id == current_user.id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    if payload.format == 'xml':
        root = ET.Element("skill", id=skill.id)
        ET.SubElement(root, "name").text = skill.name
        if skill.description:
            ET.SubElement(root, "description").text = skill.description
        if skill.category:
            ET.SubElement(root, "category").text = skill.category
        if skill.language:
            ET.SubElement(root, "language").text = skill.language
        ET.SubElement(root, "timestamp").text = str(int(skill.updated_at.timestamp() * 1000)) if skill.updated_at else "0"
        
        content_el = ET.SubElement(root, "content")
        content_el.text = f"<![CDATA[\n{skill.content}\n]]>"
        
        xml_str = ET.tostring(root, encoding="utf-8").decode("utf-8")
        xml_str = xml_str.replace("&lt;![CDATA[", "<![CDATA[").replace("]]&gt;", "]]>")
        
        safe_name = re.sub(r'[^\w\-_\. ]', '_', skill.name)
        return Response(content=xml_str, media_type="application/xml", headers={"Content-Disposition": f'attachment; filename="skill_{safe_name}.xml"'})
    
    elif payload.format == 'claude':
        frontmatter = {
            "name": skill.name,
            "version": "1.0.0",
        }
        if skill.description:
            frontmatter["description"] = skill.description
        if skill.category:
            frontmatter["category"] = skill.category
        
        yaml_str = yaml.dump(frontmatter, sort_keys=False)
        claude_str = f"---\n{yaml_str}---\n\n{skill.content}"
        
        safe_name = re.sub(r'[^\w\-_\. ]', '_', skill.name)
        return Response(content=claude_str, media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="skill_{safe_name}.md"'})
    else:
        raise HTTPException(status_code=400, detail="Unsupported format")

@skills_router.post("/{skill_id}/share", status_code=status.HTTP_200_OK)
async def share_skill(
    skill_id: str, 
    payload: PersonalitySendRequest, # Reusing same model for target_username
    current_user: UserAuthDetails = Depends(get_current_active_user), 
    db: Session = Depends(get_db)
):
    skill = db.query(DBSkill).filter(DBSkill.id == skill_id, DBSkill.owner_user_id == current_user.id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    target_user = db.query(DBUser).filter(DBUser.username == payload.target_username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    # Check for duplicates
    if db.query(DBSkill).filter(DBSkill.owner_user_id == target_user.id, DBSkill.name == skill.name).first():
        raise HTTPException(status_code=409, detail=f"User already has a skill named '{skill.name}'")

    new_skill = DBSkill(
        name=skill.name,
        description=skill.description,
        category=skill.category,
        language=skill.language,
        content=skill.content,
        owner_user_id=target_user.id
    )
    db.add(new_skill)
    try:
        db.commit()
        from backend.ws_manager import manager
        manager.send_personal_message_sync({
            "type": "notification",
            "data": {"message": f"{current_user.username} sent you a new skill: {skill.name}", "type": "success"}
        }, target_user.id)
        # Trigger a refresh on the recipient's side
        manager.send_personal_message_sync({"type": "skill_saved", "data": {"title": skill.name}}, target_user.id)
        
        return {"message": "Skill shared successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@skills_router.post("/import", response_model=SkillPublic)
async def import_skill(file: UploadFile = File(...), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    content_bytes = await file.read()
    text_content = content_bytes.decode('utf-8', errors='replace')
    
    name = "Imported Skill"
    description = ""
    category = "Imported"
    language = "markdown"
    skill_content = ""
    
    try:
        # Detect XML (Custom format)
        if "<skill" in text_content[:100]:
            cdata_match = re.search(r'<!\[CDATA\[(.*?)\]\]>', text_content, re.DOTALL)
            cdata_content = cdata_match.group(1) if cdata_match else ""
            
            clean_xml = re.sub(r'<!\[CDATA\[.*?\]\]>', '', text_content, flags=re.DOTALL)
            root = ET.fromstring(clean_xml)
            
            name_el = root.find("name")
            if name_el is not None and name_el.text: name = name_el.text
            desc_el = root.find("description")
            if desc_el is not None and desc_el.text: description = desc_el.text
            cat_el = root.find("category")
            if cat_el is not None and cat_el.text: category = cat_el.text
            lang_el = root.find("language")
            if lang_el is not None and lang_el.text: language = lang_el.text
            
            cont_el = root.find("content")
            if cdata_content:
                skill_content = cdata_content.strip()
            elif cont_el is not None and cont_el.text:
                skill_content = cont_el.text.strip()
                
        elif text_content.strip().startswith("---"):
            # Normalize newlines to prevent multiline regex anchor issues
            text_content = text_content.replace('\r\n', '\n')
            parts = re.split(r'^---[ \t]*$', text_content, maxsplit=2, flags=re.MULTILINE)
            if len(parts) >= 3:
                frontmatter_text = parts[1]
                skill_content = parts[2].strip()
                frontmatter = yaml.safe_load(frontmatter_text)
                if isinstance(frontmatter, dict):
                    name = frontmatter.get("name", name)
                    description = frontmatter.get("description", description)
                    category = frontmatter.get("category", category)
            else:
                # Fallback if split fails but starts with '---'
                skill_content = text_content.strip()
        else:
            raise ValueError("Unknown file format. Please upload a valid XML or Claude-style markdown skill file.")
            
        new_skill = DBSkill(
            name=name,
            content=skill_content,
            description=description,
            category=category,
            language=language,
            owner_user_id=current_user.id
        )
        db.add(new_skill)
        db.commit()
        db.refresh(new_skill)
        return new_skill
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to import skill: {str(e)}")