# backend/routers/admin/content_management.py
import json
import shutil
import uuid
import asyncio
import re
from typing import List, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel

from backend.db import get_db
from backend.db.models.prompt import SavedPrompt as DBSavedPrompt
from backend.db.models.fun_fact import FunFact as DBFunFact, FunFactCategory as DBFunFactCategory
from backend.db.models.datastore import DataStore as DBDataStore
from backend.models import (
    UserAuthDetails, TaskInfo, PromptCreate, PromptPublic, PromptUpdate,
    FunFactCategoryCreate, FunFactCategoryPublic, FunFactCategoryUpdate,
    FunFactCreate, FunFactPublic, FunFactUpdate,
    FunFactsImportRequest, FunFactExport, FunFactCategoryExport, FunFactCategoryImport
)
from backend.session import get_current_admin_user, get_user_temp_uploads_path, get_user_lollms_client, get_safe_store_instance
from backend.migration_utils import run_openwebui_migration
from backend.zoo_cache import force_build_full_cache
from backend.task_manager import task_manager, Task
from backend.settings import settings
from ascii_colors import trace_exception

# --- Tool Imports ---
try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

try:
    from scrapemaster import ScrapeMaster
except ImportError:
    ScrapeMaster = None

try:
    import wikipedia
except ImportError:
    wikipedia = None

content_management_router = APIRouter()

class GenerateFunFactsRequest(BaseModel):
    source_type: str = "topic" # topic, text, url, search, datastore, wikipedia
    content: str # The topic, raw text, url, search query, or prompt for datastore
    category: Optional[str] = None
    n_facts: int = 5
    datastore_id: Optional[str] = None

def _refresh_zoo_cache_task(task: Task):
    task.log("Starting Zoo cache refresh.")
    task.set_progress(10)
    force_build_full_cache()
    task.set_progress(100)
    task.log("Zoo cache refresh completed.")
    return {"message": "Zoo cache refreshed successfully."}

def _generate_fun_facts_task(task: Task, request_data: dict, username: str):
    task.log("Starting fun facts generation task...")
    
    source_type = request_data.get('source_type', 'topic')
    content_input = (request_data.get('content') or '').strip()
    category_name = request_data.get('category')
    n_facts = request_data.get('n_facts', 5)
    datastore_id = request_data.get('datastore_id')

    task.log(f"DEBUG: Input Content: '{content_input}'")
    task.log(f"DEBUG: Initial Source Type: {source_type}")

    lc = get_user_lollms_client(username)
    context_text = ""

    # Auto-correction: If source is 'topic' but content looks like a URL, switch to 'url'
    if source_type == 'topic' or source_type == 'url':
        # Check specifically for Wikipedia URLs
        if 'wikipedia.org/wiki/' in content_input:
            task.log("Wikipedia URL detected. Switching to Wikipedia mode.", "INFO")
            source_type = 'wikipedia'
        elif source_type == 'topic' and re.search(r'^(https?://|www\.)', content_input, re.IGNORECASE):
            task.log("URL pattern detected in topic field. Switching mode to URL scraping...", "INFO")
            source_type = 'url'
            if content_input.lower().startswith('www.'):
                content_input = 'https://' + content_input
                task.log(f"Normalized URL to: {content_input}")

    # 1. Gather Context based on Source Type
    task.set_progress(10)
    
    try:
        if source_type == 'topic':
            # For pure topics, we don't provide context text, we ask AI to use internal knowledge
            context_text = "" 
            task.log(f"Generating based on internal knowledge for topic: {content_input}")
            
        elif source_type == 'text':
            context_text = f"{content_input[:10000]}" # Truncate to avoid context overflow if huge
            task.log("Generating based on provided text.")

        elif source_type == 'wikipedia':
            if not wikipedia:
                error_msg = "Wikipedia library not installed. Please install 'wikipedia'."
                task.log(error_msg, "ERROR")
                raise ImportError(error_msg)
            
            task.log(f"Fetching Wikipedia content for: {content_input}")
            try:
                lang = "en"
                title = content_input
                
                # Parse URL if provided
                url_match = re.search(r'https?://(\w+)\.wikipedia\.org/wiki/(.+)', content_input)
                if url_match:
                    lang = url_match.group(1)
                    # Decode URL encoding (e.g. Marie_Curie)
                    title = url_match.group(2).replace('_', ' ')
                    # Simple URL decode if needed (mostly handles %20, etc)
                    try:
                        from urllib.parse import unquote
                        title = unquote(title)
                    except: pass
                    
                task.log(f"Setting Wikipedia language to: {lang}")
                wikipedia.set_lang(lang)
                
                try:
                    # auto_suggest=False prevents it from guessing wrong pages for exact titles
                    page = wikipedia.page(title, auto_suggest=False)
                except wikipedia.exceptions.DisambiguationError as e:
                    task.log(f"Ambiguous page '{title}'. Options: {e.options[:5]}...", "WARNING")
                    # Fallback: pick the first option
                    if e.options:
                        first_opt = e.options[0]
                        task.log(f"Selecting first option: {first_opt}")
                        page = wikipedia.page(first_opt, auto_suggest=False)
                    else:
                        raise e
                
                context_text = page.content[:15000]
                task.log(f"Retrieved Wikipedia page: '{page.title}'. Length: {len(context_text)} chars.")
                
                # If category wasn't provided, use the page title
                if not category_name:
                    category_name = page.title

            except Exception as e:
                task.log(f"Wikipedia fetch failed: {e}", "ERROR")
                raise e

        elif source_type == 'url':
            if not ScrapeMaster:
                error_msg = "ScrapeMaster library is not installed. Cannot scrape URL."
                task.log(error_msg, "ERROR")
                raise ImportError(error_msg)
                
            task.log(f"Scraping URL: {content_input}")
            try:
                # Corrected usage based on feedback
                scraper = ScrapeMaster(content_input, headless=True)
                
                # Trying scrape_markdown as suggested
                try:
                    scraped_content = scraper.scrape_markdown()
                except AttributeError:
                    task.log("scrape_markdown not found on ScrapeMaster, attempting fallback strategies...", "WARNING")
                    # Fallback to scrape_all if scrape_markdown fails or doesn't exist
                    res = scraper.scrape_all(max_depth=0, convert_to_markdown=True)
                    scraped_content = res.get('markdown', '')

                if not scraped_content or len(scraped_content.strip()) < 50:
                    task.log("Scraping returned empty or too short content. Proceeding with URL as topic...", "WARNING")
                    context_text = f"URL Topic: {content_input}"
                else:
                    context_text = scraped_content[:15000] # Increased limit
                    task.log(f"URL scraped successfully ({len(context_text)} chars).")
                    task.log(f"DEBUG: Scraped Content Snippet: {context_text[:200]}...", "INFO")

            except Exception as e:
                task.log(f"Scraping failed: {e}. Treating as topic.", "WARNING")
                trace_exception(e)
                context_text = f"Topic: {content_input}"

        elif source_type == 'search':
            if not DDGS:
                error_msg = "DuckDuckGo Search library (duckduckgo-search) not installed."
                task.log(error_msg, "ERROR")
                raise ImportError(error_msg)
                
            task.log(f"Searching for: {content_input}")
            try:
                with DDGS() as ddgs:
                    results = [r for r in ddgs.text(content_input, max_results=3)]
                    if not results:
                        task.log("No search results found.", "WARNING")
                        context_text = f"Topic: {content_input}"
                    else:
                        formatted_results = "\n".join([f"- {r['title']}: {r['body']}" for r in results])
                        context_text = formatted_results
                        task.log(f"Search complete. Found {len(results)} results.")
            except Exception as e:
                task.log(f"Search failed: {e}", "ERROR")
                context_text = f"Topic: {content_input}"

        elif source_type == 'datastore':
            if not datastore_id:
                raise ValueError("Datastore ID required for datastore source.")
            task.log(f"Querying DataStore...")
            with task.db_session_factory() as db:
                ss = get_safe_store_instance(username, datastore_id, db)
                results = ss.query(content_input, top_k=3)
                chunks = [r['chunk_text'] for r in results]
                context_text = "\n---\n".join(chunks)
            task.log("DataStore query complete.")

    except Exception as e:
        task.log(f"Error during context gathering: {e}", "ERROR")
        trace_exception(e)
        raise e

    task.set_progress(40)

    # 2. Construct Prompt & Schema
    
    # Define the JSON Schema for structured output
    fun_facts_schema = {
        "type": "object",
        "properties": {
            "category": {
                "type": "string", 
                "description": "A short category name for these facts (e.g. 'Science', 'History')."
            },
            "fun_facts": {
                "type": "array",
                "items": {"type": "string"},
                "description": f"A list of exactly {n_facts} distinct, interesting facts."
            }
        },
        "required": ["category", "fun_facts"]
    }

    # Strict instruction to enforce explicit naming in every fact
    style_instruction = "CRITICAL: Each fact must be a standalone sentence that explicitly names the subject. Do NOT use pronouns like 'He', 'She', 'It', or 'They' to start the sentence or refer to the main subject. Instead, use the full name (e.g. 'Marie Curie' instead of 'She') in every single fact."

    if context_text:
        generation_prompt = f"""
Based on the provided context, generate exactly {n_facts} interesting, unique, and verifiable fun facts.
{style_instruction}
If the context is insufficient, use your internal knowledge to supplement the facts, but prioritize the context.

[CONTEXT START]
{context_text}
[CONTEXT END]
"""
    else:
        generation_prompt = f"""
Generate exactly {n_facts} interesting, unique, and verifiable fun facts about the topic: "{content_input}".
{style_instruction}
Use your internal knowledge to find the most surprising facts.
"""

    if category_name:
         generation_prompt += f"\nThe category MUST be: '{category_name}'."
    
    task.log("Asking AI to generate structured facts...")
    
    try:
        # Utilize generate_structured_content to handle JSON generation and parsing automatically
        data = lc.generate_structured_content(
            generation_prompt, 
            schema=fun_facts_schema, 
            max_tokens=2048, 
            temperature=0.7
        )
        
        # Extended logging for debugging
        task.log(f"DEBUG: AI Raw Response Data: {json.dumps(data, indent=2)}")
        
    except Exception as e:
        task.log(f"Structured generation error: {e}", "ERROR")
        trace_exception(e)
        raise

    task.set_progress(80)

    # Validate output
    if not data or not isinstance(data, dict):
        raise ValueError(f"AI returned invalid data structure: {type(data)}. Expected dict.")
    
    facts_list = data.get("fun_facts", [])
    suggested_category = data.get("category", category_name or "General")

    if not facts_list:
        raise ValueError("AI returned a valid structure but the 'fun_facts' list is empty.")

    # Save to DB
    try:
        with task.db_session_factory() as db:
            final_category_name = category_name or suggested_category
            
            # Find or Create Category
            db_category = db.query(DBFunFactCategory).filter(DBFunFactCategory.name == final_category_name).first()
            if not db_category:
                db_category = DBFunFactCategory(name=final_category_name, is_active=True)
                db.add(db_category)
                db.flush()
            
            facts_to_add = []
            for fact_content in facts_list:
                if fact_content and isinstance(fact_content, str) and fact_content.strip():
                    facts_to_add.append(DBFunFact(content=fact_content.strip(), category_id=db_category.id))
            
            if facts_to_add:
                db.add_all(facts_to_add)
                db.commit()
                task.set_progress(100)
                task.log(f"Success! Saved {len(facts_to_add)} facts to category '{final_category_name}'.", "SUCCESS")
                return {"facts_added": len(facts_to_add), "category": final_category_name}
            else:
                task.log("No valid facts strings were found in the response list.", "WARNING")
                return {"facts_added": 0, "category": final_category_name}

    except Exception as e:
        task.log(f"Failed to save fun facts to DB. Error: {e}", "ERROR")
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
    request_data = request.model_dump()
    return task_manager.submit_task(
        name=f"Generate Fun Facts ({request.source_type})",
        target=_generate_fun_facts_task,
        args=(request_data, current_admin_user.username),
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
