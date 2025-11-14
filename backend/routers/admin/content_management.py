# [UPDATE] backend/routers/admin/content_management.py
import json
import shutil
import uuid
from typing import List, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel

from backend.db import get_db
from backend.db.models.prompt import SavedPrompt as DBSavedPrompt
from backend.db.models.fun_fact import FunFact as DBFunFact, FunFactCategory as DBFunFactCategory
from backend.models import (
    UserAuthDetails, TaskInfo, PromptCreate, PromptPublic, PromptUpdate,
    FunFactCategoryCreate, FunFactCategoryPublic, FunFactCategoryUpdate,
    FunFactCreate, FunFactPublic, FunFactUpdate,
    FunFactsImportRequest, FunFactExport, FunFactCategoryExport, FunFactCategoryImport
)
from backend.session import get_current_admin_user, get_user_temp_uploads_path, get_user_lollms_client
from backend.migration_utils import run_openwebui_migration
from backend.zoo_cache import force_build_full_cache
from backend.task_manager import task_manager, Task

content_management_router = APIRouter()

class GenerateFunFactsRequest(BaseModel):
    prompt: str
    category: Optional[str] = None

def _refresh_zoo_cache_task(task: Task):
    task.log("Starting Zoo cache refresh.")
    task.set_progress(10)
    force_build_full_cache()
    task.set_progress(100)
    task.log("Zoo cache refresh completed.")
    return {"message": "Zoo cache refreshed successfully."}

def _generate_fun_facts_task(task: Task, prompt: str, category: Optional[str], username: str):
    task.log("Starting fun facts generation task...")
    
    lc = get_user_lollms_client(username)
    task.set_progress(10)

    generation_prompt = f"""
Generate a list of interesting and verifiable fun facts about the following topic.
The output must be a single, valid JSON object containing a single key "fun_facts", which is a list of strings.
Each string in the list should be a single fun fact.
Generate at least 5 facts.

Topic:
---
{prompt}
---

Return ONLY the JSON object.
"""
    if category:
            generation_prompt += f'\nThe fun facts should relate to the category: "{category}"'
    data = lc.generate_structured_content(generation_prompt,schema={'fun_facts':"a list of texts each one is a fun fact","category":"the category of the fun facts"}, max_tokens=1000, temperature=0.7, top_p=0.9, stop_sequences=None)
    task.set_progress(80)

    try:
        facts_list = data.get("fun_facts", [])
        category = data.get("category", category)

        if not facts_list:
            raise ValueError("AI did not return any facts.")

        with task.db_session_factory() as db:
            category_name = category or "unknonwn"
            db_category = db.query(DBFunFactCategory).filter(DBFunFactCategory.name == category_name).first()
            if not db_category:
                db_category = DBFunFactCategory(name=category_name, is_active=True)
                db.add(db_category)
                db.flush()
            
            facts_to_add = [DBFunFact(content=fact_content, category_id=db_category.id) for fact_content in facts_list if fact_content.strip()]
            db.add_all(facts_to_add)
            db.commit()

            task.set_progress(100)
            task.log(f"Generated and saved {len(facts_to_add)} fun facts to category '{category_name}'.")
            return {"facts_added": len(facts_to_add), "category": category_name}

    except Exception as e:
        task.log(f"Failed to parse AI response or save fun facts. Error: {e}\nRaw Response: {response}", "ERROR")
        raise

@content_management_router.post("/refresh-zoo-cache", response_model=TaskInfo, status_code=202)
async def refresh_zoo_cache_endpoint(current_user: UserAuthDetails = Depends(get_current_admin_user)):
    return task_manager.submit_task(
        name="Refreshing Zoo Cache",
        target=_refresh_zoo_cache_task,
        description="Scanning all Zoo repositories and rebuilding the cache.",
        owner_username=current_user.username
    )

@content_management_router.post("/import-openwebui", response_model=Dict[str, str])
async def import_openwebui_data(
    file: UploadFile = File(...),
    current_admin: UserAuthDetails = Depends(get_current_admin_user)
):
    if not file or file.filename != "webui.db":
        raise HTTPException(status_code=400, detail="Invalid file. Please upload 'webui.db'.")

    temp_import_dir = get_user_temp_uploads_path(current_admin.username) / f"owui_import_{uuid.uuid4()}"
    temp_import_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(temp_import_dir / file.filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()

    task_manager.submit_task(
        name="Import OpenWebUI Data",
        target=run_openwebui_migration,
        args=(str(temp_import_dir),),
        description=f"Migrating data from {file.filename}",
        owner_username=current_admin.username
    )
    return {"message": "Migration started. Check Task Manager for progress."}

@content_management_router.get("/fun-facts/categories", response_model=List[FunFactCategoryPublic])
async def get_fun_fact_categories(db: Session = Depends(get_db)):
    return db.query(DBFunFactCategory).order_by(DBFunFactCategory.name).all()

@content_management_router.post("/fun-facts/categories", response_model=FunFactCategoryPublic, status_code=status.HTTP_201_CREATED)
async def create_fun_fact_category(category_data: FunFactCategoryCreate, db: Session = Depends(get_db)):
    if db.query(DBFunFactCategory).filter(DBFunFactCategory.name == category_data.name).first():
        raise HTTPException(status_code=409, detail="A category with this name already exists.")
    new_category = DBFunFactCategory(**category_data.model_dump())
    db.add(new_category)
    db.commit()
    db.refresh(new_category)
    return new_category

@content_management_router.put("/fun-facts/categories/{category_id}", response_model=FunFactCategoryPublic)
async def update_fun_fact_category(category_id: int, update_data: FunFactCategoryUpdate, db: Session = Depends(get_db)):
    category = db.query(DBFunFactCategory).filter(DBFunFactCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found.")
    
    update_dict = update_data.model_dump(exclude_unset=True)
    if 'name' in update_dict and update_dict['name'] != category.name:
        if db.query(DBFunFactCategory).filter(DBFunFactCategory.name == update_dict['name']).first():
            raise HTTPException(status_code=409, detail="A category with this name already exists.")

    for key, value in update_dict.items():
        setattr(category, key, value)
    
    db.commit()
    db.refresh(category)
    return category

@content_management_router.delete("/fun-facts/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fun_fact_category(category_id: int, db: Session = Depends(get_db)):
    category = db.query(DBFunFactCategory).filter(DBFunFactCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found.")
    
    db.query(DBFunFact).filter(DBFunFact.category_id == category_id).delete()
    db.delete(category)
    db.commit()

@content_management_router.get("/fun-facts", response_model=List[FunFactPublic])
async def get_all_fun_facts(db: Session = Depends(get_db)):
    return db.query(DBFunFact).options(joinedload(DBFunFact.category)).order_by(DBFunFact.id.desc()).all()

@content_management_router.post("/fun-facts", response_model=FunFactPublic, status_code=status.HTTP_201_CREATED)
async def create_fun_fact(fact_data: FunFactCreate, db: Session = Depends(get_db)):
    if not db.query(DBFunFactCategory).filter(DBFunFactCategory.id == fact_data.category_id).first():
        raise HTTPException(status_code=404, detail="Category not found.")
    new_fact = DBFunFact(**fact_data.model_dump())
    db.add(new_fact)
    db.commit()
    db.refresh(new_fact)
    return new_fact

@content_management_router.put("/fun-facts/{fact_id}", response_model=FunFactPublic)
async def update_fun_fact(fact_id: int, update_data: FunFactUpdate, db: Session = Depends(get_db)):
    fact = db.query(DBFunFact).filter(DBFunFact.id == fact_id).first()
    if not fact:
        raise HTTPException(status_code=404, detail="Fun fact not found.")
    
    update_dict = update_data.model_dump(exclude_unset=True)
    if 'category_id' in update_dict:
        if not db.query(DBFunFactCategory).filter(DBFunFactCategory.id == update_dict['category_id']).first():
            raise HTTPException(status_code=404, detail="New category not found.")

    for key, value in update_dict.items():
        setattr(fact, key, value)
        
    db.commit()
    db.refresh(fact)
    return fact

@content_management_router.delete("/fun-facts/{fact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fun_fact(fact_id: int, db: Session = Depends(get_db)):
    fact = db.query(DBFunFact).filter(DBFunFact.id == fact_id).first()
    if not fact:
        raise HTTPException(status_code=404, detail="Fun fact not found.")
    db.delete(fact)
    db.commit()

@content_management_router.post("/fun-facts/generate-from-prompt", response_model=TaskInfo, status_code=202)
async def generate_fun_facts_from_prompt(
    request: GenerateFunFactsRequest,
    current_admin_user: UserAuthDetails = Depends(get_current_admin_user)
):
    return task_manager.submit_task(
        name=f"Generate Fun Facts for '{request.prompt[:30]}...'",
        target=_generate_fun_facts_task,
        args=(request.prompt, request.category, current_admin_user.username),
        owner_username=current_admin_user.username
    )

@content_management_router.post("/fun-facts/import", response_model=Dict[str, int])
async def import_fun_facts(import_data: FunFactsImportRequest, db: Session = Depends(get_db)):
    existing_categories = {cat.name: cat.id for cat in db.query(DBFunFactCategory).all()}
    created_categories = 0
    created_facts = 0
    
    for item in import_data.fun_facts:
        category_id = existing_categories.get(item.category)
        if not category_id:
            new_cat = DBFunFactCategory(name=item.category, is_active=True)
            db.add(new_cat)
            db.flush()
            category_id = new_cat.id
            existing_categories[item.category] = category_id
            created_categories += 1
        
        db.add(DBFunFact(content=item.content, category_id=category_id))
        created_facts += 1
    
    db.commit()
    return {"categories_created": created_categories, "facts_created": created_facts}

@content_management_router.get("/fun-facts/export", response_model=List[FunFactExport])
async def export_fun_facts(db: Session = Depends(get_db)):
    all_facts = db.query(DBFunFact).options(joinedload(DBFunFact.category)).all()
    return [FunFactExport(category=fact.category.name, content=fact.content) for fact in all_facts]
    
@content_management_router.get("/fun-facts/categories/{category_id}/export", response_model=FunFactCategoryExport)
async def export_fun_fact_category(category_id: int, db: Session = Depends(get_db)):
    category = db.query(DBFunFactCategory).filter(DBFunFactCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found.")
    
    facts = [fact.content for fact in db.query(DBFunFact.content).filter(DBFunFact.category_id == category_id).all()]
    
    export_data = FunFactCategoryExport(name=category.name, is_active=category.is_active, color=category.color, facts=facts)
    
    headers = {'Content-Disposition': f'attachment; filename="fun_facts_{category.name}.json"'}
    return JSONResponse(content=export_data.model_dump(), headers=headers)

@content_management_router.post("/fun-facts/categories/import", response_model=Dict[str, int])
async def import_fun_fact_category(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        data = json.loads(await file.read())
        import_data = FunFactCategoryImport(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file or format: {e}")
    finally:
        await file.close()

    category = db.query(DBFunFactCategory).filter(DBFunFactCategory.name == import_data.name).first()
    categories_created = 0
    if not category:
        category = DBFunFactCategory(name=import_data.name, is_active=import_data.is_active, color=import_data.color)
        db.add(category)
        db.flush()
        categories_created = 1

    facts_created = sum(1 for _ in import_data.facts)
    for fact_content in import_data.facts:
        db.add(DBFunFact(content=fact_content, category_id=category.id))
    
    db.commit()
    return {"categories_created": categories_created, "facts_created": facts_created}
