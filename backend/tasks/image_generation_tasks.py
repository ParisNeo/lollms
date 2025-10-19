# backend/tasks/image_generation_tasks.py
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

def _generate_image_task(task: Task, username: str, discussion_id: str, prompt: str, negative_prompt: str, width: Optional[int], height: Optional[int], generation_params: dict):
    task.log("Starting image generation task...")
    task.set_progress(5)

    with task.db_session_factory() as db:
        user = db.query(DBUser).filter(DBUser.username == username).first()
        if not user:
            raise Exception(f"User '{username}' not found.")

        user_tti_model_full = user.tti_binding_model_name
        
        selected_binding = None
        selected_model_name = None
        binding_config = {}

        if user_tti_model_full and '/' in user_tti_model_full:
            binding_alias, model_name = user_tti_model_full.split('/', 1)
            selected_binding = db.query(DBTTIBinding).filter(DBTTIBinding.alias == binding_alias, DBTTIBinding.is_active == True).first()
            selected_model_name = model_name
        
        if not selected_binding:
            task.log("User's preferred TTI model not found or not set. Falling back to the first available active TTI binding.", "WARNING")
            selected_binding = db.query(DBTTIBinding).filter(DBTTIBinding.is_active == True).order_by(DBTTIBinding.id).first()
            if selected_binding:
                selected_model_name = selected_binding.default_model_name
        
        if not selected_binding:
            raise Exception("No active TTI (Text-to-Image) binding found in system settings.")
        
        task.log(f"Using TTI binding: {selected_binding.alias}")
        if selected_model_name:
            task.log(f"Using TTI model: {selected_model_name}")
        
        binding_config = selected_binding.config.copy() if selected_binding.config else {}
        
        model_aliases = selected_binding.model_aliases or {}
        alias_info = model_aliases.get(selected_model_name)
        
        if alias_info:
            task.log(f"Applying settings from model alias '{alias_info.get('title', selected_model_name)}'.")
            for key, value in alias_info.items():
                if key not in ['title', 'description', 'icon'] and value is not None:
                    binding_config[key] = value
        
        allow_override = (alias_info or {}).get('allow_parameters_override', True)
        if allow_override:
            user_configs = user.tti_models_config or {}
            model_user_config = user_configs.get(user_tti_model_full)
            if model_user_config:
                task.log("Applying user-specific settings for this model.")
                for key, value in model_user_config.items():
                    if value is not None:
                        binding_config[key] = value
        else:
            task.log("User overrides are disabled by admin for this model alias.")

        if selected_model_name:
            binding_config['model_name'] = selected_model_name
            
        task.set_progress(10)

    try:
        lc = LollmsClient(
            tti_binding_name=selected_binding.name,
            tti_binding_config=binding_config
        )
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
        if not model_full_name or '/' not in model_full_name:
            raise Exception("A valid TTI model must be selected.")

        tti_binding_alias, tti_model_name = model_full_name.split('/', 1)
        
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
                model=model_full_name,
                width=generation_params.get("width"),
                height=generation_params.get("height")
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
    configuration for parameter overrides (same logic as generation).
    """
    task.log("Starting image studio edit task...")
    task.set_progress(5)

    with task.db_session_factory() as db:
        # ------------------------------------------------------------------
        # 1️⃣ Retrieve user and ensure a valid model is selected
        # ------------------------------------------------------------------
        user = db.query(DBUser).filter(DBUser.username == username).first()
        if not user:
            raise Exception(f"User '{username}' not found.")

        model_full_name = request_data.get('model') or user.tti_binding_model_name
        if not model_full_name or '/' not in model_full_name:
            raise Exception("A valid TTI model must be selected.")

        # ------------------------------------------------------------------
        # 2️⃣ Resolve binding, model and configuration (admin + user overrides)
        # ------------------------------------------------------------------
        tti_binding_alias, tti_model_name = model_full_name.split('/', 1)

        # Fetch the binding record
        selected_binding = db.query(DBTTIBinding).filter(
            DBTTIBinding.alias == tti_binding_alias,
            DBTTIBinding.is_active == True
        ).first()

        if not selected_binding:
            # Fallback to first active binding (mirrors generation fallback)
            task.log(
                f"Binding alias '{tti_binding_alias}' not found or inactive. "
                "Falling back to first active TTI binding.", "WARNING"
            )
            selected_binding = db.query(DBTTIBinding).filter(
                DBTTIBinding.is_active == True
            ).order_by(DBTTIBinding.id).first()
            if not selected_binding:
                raise Exception("No active TTI (Text-to-Image) binding found in system settings.")

        # Base config from the binding
        binding_config = selected_binding.config.copy() if selected_binding.config else {}

        # ------------------------------------------------------------------
        # 3️⃣ Apply model‑alias defaults (if any)
        # ------------------------------------------------------------------
        model_aliases = selected_binding.model_aliases or {}
        alias_info = model_aliases.get(tti_model_name)

        if alias_info:
            task.log(
                f"Applying alias defaults for model '{alias_info.get('title', tti_model_name)}'."
            )
            for key, value in alias_info.items():
                if key not in ['title', 'description', 'icon'] and value is not None:
                    binding_config[key] = value

        # Determine if admin allows user overrides for this model
        allow_override = (alias_info or {}).get('allow_parameters_override', True)

        # ------------------------------------------------------------------
        # 4️⃣ Merge user‑specific overrides when permitted
        # ------------------------------------------------------------------
        if allow_override:
            user_configs = user.tti_models_config or {}
            model_user_config = user_configs.get(model_full_name)
            if model_user_config:
                task.log("Applying user‑specific overrides for this model.")
                for key, value in model_user_config.items():
                    if value is not None:
                        binding_config[key] = value
        else:
            task.log(
                "Admin has disabled parameter overrides for this model alias.", "WARNING"
            )

        # Ensure the model name is set in the final config
        binding_config['model_name'] = tti_model_name

        print(f"binding_config: {binding_config}")
        # ------------------------------------------------------------------
        # 5️⃣ Initialise the Lollms client with the resolved config
        # ------------------------------------------------------------------
        lc = LollmsClient(
            tti_binding_name=selected_binding.name,
            tti_binding_config=binding_config
        )
        if not lc.tti:
            raise Exception(f"TTI binding '{selected_binding.name}' is not available.")
        task.log("LollmsClient initialized for image editing.")
        task.set_progress(20)

        # ------------------------------------------------------------------
        # 6️⃣ Load source images (base64 or from stored files)
        # ------------------------------------------------------------------
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

        # ------------------------------------------------------------------
        # 7️⃣ Build generation parameters (respecting overrides logic)
        # ------------------------------------------------------------------
        # Start with any parameters supplied in the request
        generation_params = {
            "prompt": request_data.get('prompt', ''),
            "negative_prompt": request_data.get('negative_prompt'),
            "mask": request_data.get('mask'),
            "seed": request_data.get('seed', -1),
            "sampler_name": request_data.get('sampler_name'),
            "steps": request_data.get('steps'),
            "cfg_scale": request_data.get('cfg_scale'),
            "width": request_data.get('width'),
            "height": request_data.get('height'),
        }

        # Remove keys that are None to avoid sending unwanted defaults
        generation_params = {k: v for k, v in generation_params.items() if v is not None}

        task.log("Sending edit request to TTI binding...")
        edited_image_bytes = lc.tti.edit_image(
            images=source_images_b64,
            **generation_params
        )
        task.set_progress(80)

        if not edited_image_bytes:
            raise Exception("Image editing failed to return data.")

        # ------------------------------------------------------------------
        # 8️⃣ Persist the edited image
        # ------------------------------------------------------------------
        filename = f"{uuid.uuid4().hex}.png"
        file_path = user_images_path / filename
        with open(file_path, "wb") as f:
            f.write(edited_image_bytes)

        new_image = UserImage(
            id=str(uuid.uuid4()),
            owner_user_id=user.id,
            filename=filename,
            prompt=f"Edited from {len(source_images_b64)} image(s): {request_data.get('prompt')}",
            model=model_full_name,
            width=request_data.get("width"),
            height=request_data.get("height")
        )
        db.add(new_image)
        db.commit()
        db.refresh(new_image)

        task.log("Image editing completed and saved.")
        task.set_progress(100)

        # Return the newly created image data in the public schema
        return json.loads(UserImagePublic.from_orm(new_image).model_dump_json())