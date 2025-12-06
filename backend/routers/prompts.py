# backend/routers/prompts.py
from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from packaging import version as packaging_version

from backend.db import get_db
from backend.db.models.prompt import SavedPrompt as DBSavedPrompt
from backend.db.models.dm import DirectMessage as DBDirectMessage
from backend.db.models.user import User as DBUser
from backend.db.models.db_task import DBTask
from backend.models import UserAuthDetails, PromptCreate, PromptPublic, PromptUpdate, PromptShareRequest, PromptsExport, PromptsImport, GeneratePromptRequest, TaskInfo
from backend.session import get_current_active_user, get_user_lollms_client
from backend.ws_manager import manager
from backend.task_manager import task_manager, Task
from backend.settings import settings
from backend.zoo_cache import get_all_items

prompts_router = APIRouter(
    prefix="/api/prompts",
    tags=["Prompts"],
    dependencies=[Depends(get_current_active_user)]
)

def _to_task_info(db_task: DBTask) -> TaskInfo:
    """Converts a DBTask SQLAlchemy model to a TaskInfo Pydantic model."""
    if not db_task:
        return None
    return TaskInfo(
        id=db_task.id, name=db_task.name, description=db_task.description,
        status=db_task.status, progress=db_task.progress,
        logs=[log for log in (db_task.logs or [])], result=db_task.result, error=db_task.error,
        created_at=db_task.created_at, started_at=db_task.started_at, completed_at=db_task.completed_at,
        file_name=db_task.file_name, total_files=db_task.total_files,
        owner_username=db_task.owner.username if db_task.owner else "System"
    )

def _generate_prompt_task(task: Task, username: str, user_prompt: str):
    task.log("Starting prompt generation...")
    task.set_progress(10)
    
    with task.db_session_factory() as db:
        lc = get_user_lollms_client(username)
        current_user = db.query(DBUser).filter(DBUser.username == username).first()
        if not current_user:
            raise Exception("User not found for prompt generation task.")

        prompt_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "A short, descriptive name for the prompt."},
                "category": {"type": "string", "description": "A category for the prompt (e.g., 'Writing', 'Coding')."},
                "description": {"type": "string", "description": "A brief description of what the prompt does."},
                "content": {"type": "string", "description": "The full content of the prompt itself, including placeholders if needed."},
                "icon": {"type": "string", "description": "Optional: a base64 encoded icon for the prompt. Can be empty."}
            },
            "required": ["name", "content"],
            "description": "JSON object defining a LoLLMs saved prompt."
        }
        
        system_prompt = """You are an expert prompt designer. Create a new prompt based on the user's request. The author will be set automatically.
When creating the prompt content, you can use LoLLMs placeholders to make it interactive. Here's how they work:

1.  **Simple Placeholder**: For a basic text input field, use `@<placeholder_name>@`.
    Example: `Summarize the following text: @<text_to_summarize>@`

2.  **Advanced Placeholder**: For more control, you can define a form with fields like title, type, options, default value, and help text. Use the following block format:
    ```
    @<name>@
    title: The title displayed to the user
    type: str | text | int | float | bool
    options: option1, option2, option3
    default: A default value
    help: A helpful tip for the user.
    @</name>@
    ```
    - `title`: The label for the input field.
    - `type`: Can be `str` (single-line text), `text` (multi-line text area), `int` (integer), `float` (number with decimals), or `bool` (checkbox).
    - `options`: (Optional) A comma-separated list of choices for a dropdown menu.
    - `default`: (Optional) The pre-filled value for the field.
    - `help`: (Optional) A tooltip to guide the user.

Example of an advanced placeholder in a prompt:
```
Translate the following text to @<language>@.

@<language>@
title: Target Language
type: str
options: English, French, Spanish, German
default: French
help: Select the language you want to translate the text into.
@</language>@
```"""
        
        task.log("Sending request to LLM for structured prompt generation...")
        task.set_progress(30)
        
        generated_data = lc.generate_structured_content(
            user_prompt,
            system_prompt=system_prompt,
            schema=prompt_schema,
            #n_predict=settings.get("default_llm_ctx_size", 4096)
        )

        task.log("Creating new prompt in the database...")
        task.set_progress(90)
        
        if db.query(DBSavedPrompt).filter(DBSavedPrompt.owner_user_id == current_user.id, DBSavedPrompt.name == generated_data.get("name")).first():
            task.log(f"Prompt '{generated_data.get('name')}' already exists. Appending UUID.", "WARNING")
            generated_data["name"] = f"{generated_data.get('name')} {task.id.split('-')[0]}"

        new_prompt = DBSavedPrompt(
            **generated_data,
            author=current_user.username,
            owner_user_id=current_user.id
        )
        db.add(new_prompt)
        db.commit()
        db.refresh(new_prompt)

        task.log("Prompt created successfully.")
        task.set_progress(100)
        
        return PromptPublic.from_orm(new_prompt).model_dump(mode='json')

@prompts_router.post("/generate-with-ai", response_model=TaskInfo, status_code=202)
async def generate_prompt_from_prompt(
    payload: GeneratePromptRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
):
    """
    Triggers a background task to generate a new user-owned prompt using AI.
    """
    db_task = task_manager.submit_task(
        name=f"Generate Prompt: {payload.prompt[:30]}...",
        target=_generate_prompt_task,
        args=(current_user.username, payload.prompt),
        description=f"Generating a new prompt based on the request: '{payload.prompt[:100]}...'",
        owner_username=current_user.username
    )
    return db_task

@prompts_router.get("", response_model=Dict[str, List[PromptPublic]])
def get_prompts(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    user_prompts_db = db.query(DBSavedPrompt).filter(DBSavedPrompt.owner_user_id == current_user.id).order_by(DBSavedPrompt.name).all()
    system_prompts_db = db.query(DBSavedPrompt).filter(DBSavedPrompt.owner_user_id.is_(None)).order_by(DBSavedPrompt.name).all()
    
    zoo_prompts_meta = { (item['repository'], item['folder_name']): item for item in get_all_items('prompt') }
    
    system_prompts_public = []
    for p in system_prompts_db:
        prompt_public = PromptPublic.from_orm(p)
        if p.repository and p.folder_name:
            zoo_key = (p.repository, p.folder_name)
            zoo_item = zoo_prompts_meta.get(zoo_key)
            if zoo_item:
                prompt_public.repo_version = str(zoo_item.get('version', 'N/A'))
                try:
                    installed_ver = str(p.version or '0.0.0')
                    repo_ver = str(zoo_item.get('version', '0.0.0'))
                    if packaging_version.parse(repo_ver) > packaging_version.parse(installed_ver):
                        prompt_public.update_available = True
                except (packaging_version.InvalidVersion, TypeError):
                    pass # Ignore version parsing errors
        system_prompts_public.append(prompt_public)
        
    user_prompts_public = [PromptPublic.from_orm(p) for p in user_prompts_db]

    return {
        "user_prompts": user_prompts_public,
        "system_prompts": system_prompts_public
    }

@prompts_router.post("", response_model=PromptPublic, status_code=status.HTTP_201_CREATED)
def create_saved_prompt(
    prompt_data: PromptCreate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # For user-created prompts, the author is always the user.
    new_prompt = DBSavedPrompt(
        **prompt_data.model_dump(),
        owner_user_id=current_user.id
    )
    db.add(new_prompt)
    try:
        db.commit()
        db.refresh(new_prompt)
        return new_prompt
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"A prompt with the name '{prompt_data.name}' already exists in your collection."
        )


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
    
    # Check for name conflict if name is being changed
    if 'name' in update_data and update_data['name'] != prompt_to_update.name:
        existing = db.query(DBSavedPrompt).filter(
            DBSavedPrompt.id != prompt_id,
            DBSavedPrompt.owner_user_id == current_user.id,
            DBSavedPrompt.name == update_data['name']
        ).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"A prompt with the name '{update_data['name']}' already exists in your collection."
            )

    for key, value in update_data.items():
        setattr(prompt_to_update, key, value)
    
    try:
        db.commit()
        db.refresh(prompt_to_update)
        return prompt_to_update
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A prompt with that name already exists."
        )

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