# [UPDATE] backend/tasks/image_generation_tasks.py
import base64
import uuid
import json
from typing import Optional
import traceback

from ascii_colors import trace_exception
from lollms_client import LollmsClient

from backend.db.models.config import TTIBinding as DBTTIBinding
from backend.db.models.user import User as DBUser
from backend.discussion import get_user_discussion
from backend.session import (
    build_lollms_client_from_params,
    get_user_images_path
)
from backend.task_manager import Task
from backend.db.models.image import UserImage
from backend.models.image import UserImagePublic
from backend.settings import settings

def _generate_image_task(task: Task, username: str, discussion_id: str, prompt: str, negative_prompt: str, width: Optional[int], height: Optional[int], generation_params: dict):
    task.log("Starting image generation task...")
    task.set_progress(5)

    try:
        # This task does not receive model override from UI, so pass None to client builder
        # The builder will automatically handle admin force settings, then user defaults.
        lc = build_lollms_client_from_params(
            username=username,
            tti_binding_alias=None,
            tti_model_name=None
        )
        if not lc.tti:
            raise Exception("No active TTI (Text-to-Image) binding found or configured.")
        
        task.log("LollmsClient initialized for TTI.")
        task.set_progress(20)

        image_bytes = lc.tti.generate_image(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            **generation_params
        )
        task.log("Image data received from binding.")
        task.set_progress(80)

        if not image_bytes:
            raise Exception("TTI binding returned empty image data.")

        b64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        discussion = get_user_discussion(username, discussion_id)
        if not discussion:
            raise Exception("Discussion not found after image generation.")
        
        discussion.add_discussion_image(b64_image, source="generation")
        discussion.commit()
        task.log("Image added to discussion and saved.")
        task.set_progress(100)
        
        all_images_info = discussion.get_discussion_images()
        
        return {
            "discussion_id": discussion_id,
            "zone": "discussion_images",
            "discussion_images": [img_info['data'] for img_info in all_images_info],
            "active_discussion_images": [img_info['active'] for img_info in all_images_info]
        }
    except Exception as e:
        task.log(f"Image generation failed: {e}", "ERROR")
        trace_exception(e)
        raise e

def _image_studio_generate_task(task: Task, username: str, request_data: dict):
    task.log("Starting image studio generation task...")
    task.set_progress(5)

    with task.db_session_factory() as db:
        user = db.query(DBUser).filter(DBUser.username == username).first()
        if not user:
            raise Exception(f"User '{username}' not found.")

        model_full_name = request_data.get('model') or user.tti_binding_model_name
        
        tti_binding_alias = None
        tti_model_name = None
        if model_full_name and '/' in model_full_name:
            tti_binding_alias, tti_model_name = model_full_name.split('/', 1)
        else:
            # If no alias is specified, we must find the default one from the database.
            default_tti_binding = db.query(DBTTIBinding).filter(DBTTIBinding.is_active == True).order_by(DBTTIBinding.id).first()
            if default_tti_binding:
                tti_binding_alias = default_tti_binding.alias
            else:
                raise Exception("No active TTI binding found to determine a default.")

        lc = build_lollms_client_from_params(
            username=username,
            tti_binding_alias=tti_binding_alias,
            tti_model_name=tti_model_name
        )
        if not lc.tti:
            raise Exception(f"TTI binding '{tti_binding_alias}' is not available.")

        user_images_path = get_user_images_path(username)
        generated_images_data = []

        generation_params = request_data.copy()
        
        # Use the determined alias and the model name from the configured client
        effective_model_full_name = f"{tti_binding_alias}/{lc.tti.config.get('model_name')}"
        generation_params.pop('model', None)
        n_images = generation_params.pop('n', 1)
        size_str = generation_params.pop('size', "1024x1024")
        
        try:
            width_str, height_str = size_str.split('x')
            generation_params["width"] = int(width_str)
            generation_params["height"] = int(height_str)
        except ValueError:
            task.log(f"Invalid size format '{size_str}'. Using default 1024x1024.", "WARNING")
            generation_params["width"] = 1024
            generation_params["height"] = 1024


        for i in range(n_images):
            if task.cancellation_event.is_set():
                task.log("Task cancelled by user.", "WARNING")
                break
            task.log(f"Generating image {i+1}/{n_images}...")
            image_bytes = lc.tti.generate_image(**generation_params)
            
            filename = f"{uuid.uuid4().hex}.png"
            file_path = user_images_path / filename
            with open(file_path, "wb") as f:
                f.write(image_bytes)
            
            new_image = UserImage(
                id=str(uuid.uuid4()),
                owner_user_id=user.id,
                filename=filename,
                prompt=request_data.get('prompt'),
                negative_prompt=request_data.get('negative_prompt'),
                model=effective_model_full_name,
                width=generation_params.get("width"),
                height=generation_params.get("height"),
                seed=generation_params.get("seed"),
                generation_params=generation_params
            )
            db.add(new_image)
            db.commit()
            db.refresh(new_image)

            generated_images_data.append(json.loads(UserImagePublic.from_orm(new_image).model_dump_json()))
            
            task.set_progress(5 + int(90 * (i + 1) / n_images))

    task.log("Image generation completed.")
    task.set_progress(100)
    return generated_images_data

def _image_studio_edit_task(task: Task, username: str, request_data: dict):
    """
    Edit images using the selected TTI binding while respecting admin
    configuration for parameter overrides.
    """
    task.log("Starting image studio edit task...")
    task.set_progress(5)

    with task.db_session_factory() as db:
        user = db.query(DBUser).filter(DBUser.username == username).first()
        if not user:
            raise Exception(f"User '{username}' not found.")

        model_full_name = request_data.get('model') or user.iti_binding_model_name
        
        tti_binding_alias = None
        tti_model_name = None
        if model_full_name and '/' in model_full_name:
            tti_binding_alias, tti_model_name = model_full_name.split('/', 1)
        else:
            default_tti_binding = db.query(DBTTIBinding).filter(DBTTIBinding.is_active == True).order_by(DBTTIBinding.id).first()
            if default_tti_binding:
                tti_binding_alias = default_tti_binding.alias
            else:
                raise Exception("No active TTI binding found to determine a default for editing.")

        # Separate runtime params from the main payload for client configuration
        runtime_params = {k: v for k, v in request_data.items() if k not in ['model', 'image_ids', 'base_image_b64']}

        lc = build_lollms_client_from_params(
            username=username,
            tti_binding_alias=tti_binding_alias,
            tti_model_name=tti_model_name,
            tti_params=runtime_params
        )

        if not lc.tti:
            raise Exception("TTI binding is not available or could not be initialized.")
            
        effective_model_full_name = f"{tti_binding_alias}/{lc.tti.config.get('model_name')}"

        task.log(f"LollmsClient initialized for image editing with model {effective_model_full_name}.")
        task.set_progress(20)
        
        user_images_path = get_user_images_path(username)
        source_images_b64 = []

        if request_data.get('base_image_b64'):
            task.log("Using provided base64 image for editing.")
            source_images_b64.append(request_data['base_image_b64'])
        else:
            task.log("Loading source images from file...")
            image_ids = request_data.get('image_ids', [])
            if not image_ids:
                raise ValueError("No source image provided for editing.")
            for image_id in image_ids:
                image_record = db.query(UserImage).filter(
                    UserImage.id == image_id,
                    UserImage.owner_user_id == user.id
                ).first()
                if image_record:
                    file_path = user_images_path / image_record.filename
                    if file_path.is_file():
                        with open(file_path, "rb") as f:
                            source_images_b64.append(base64.b64encode(f.read()).decode('utf-8'))

        if not source_images_b64:
            raise Exception("No valid source images found for editing.")
        task.set_progress(30)

        # The client is now pre-configured with all parameters.
        # We only need to pass the required `images` argument to the method.
        task.log("Sending edit request to TTI binding...")
        edited_image_bytes = lc.tti.edit_image(
            images=source_images_b64,
            **runtime_params
        )
        task.set_progress(80)

        if not edited_image_bytes:
            raise Exception("Image editing failed to return data.")

        filename = f"{uuid.uuid4().hex}.png"
        file_path = user_images_path / filename
        with open(file_path, "wb") as f:
            f.write(edited_image_bytes)

        new_image = UserImage(
            id=str(uuid.uuid4()),
            owner_user_id=user.id,
            filename=filename,
            prompt=f"Edited from {len(source_images_b64)} image(s): {request_data.get('prompt')}",
            negative_prompt=request_data.get('negative_prompt'),
            model=effective_model_full_name,
            width=request_data.get("width"),
            height=request_data.get("height"),
            seed=request_data.get("seed"),
            generation_params=runtime_params
        )
        db.add(new_image)
        db.commit()
        db.refresh(new_image)

        task.log("Image editing completed and saved.")
        task.set_progress(100)

        return json.loads(UserImagePublic.from_orm(new_image).model_dump_json())