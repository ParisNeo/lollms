# [UPDATE] backend/tasks/image_generation_tasks.py
import base64
import uuid
import json
from typing import Optional
import traceback
import datetime
from pathlib import Path
import os

from ascii_colors import trace_exception
from lollms_client import LollmsClient

from backend.db.models.config import TTIBinding as DBTTIBinding
from backend.db.models.user import User as DBUser
from backend.db.models.personality import Personality as DBPersonality
from backend.discussion import get_user_discussion
from backend.session import (
    build_lollms_client_from_params,
    get_user_images_path
)
from backend.task_manager import Task
from backend.db.models.image import UserImage
from backend.models.image import UserImagePublic, ImagePromptEnhancementRequest, TimelapseRequest
from backend.settings import settings

# Attempt to import moviepy for video generation
try:
    from moviepy.editor import ImageClip, concatenate_videoclips
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False

def _generate_image_task(task: Task, username: str, discussion_id: str, prompt: str, negative_prompt: str, width: Optional[int], height: Optional[int], generation_params: dict, parent_message_id: Optional[str] = None):
    # ... (existing code for _generate_image_task remains the same)
    task.log("Starting image generation task...")
    task.set_progress(5)
    task.set_description("Initializing TTI client...")

    try:
        lc = build_lollms_client_from_params(
            username=username,
            tti_binding_alias=None,
            tti_model_name=None
        )
        if not lc.tti:
            raise Exception("No active TTI (Text-to-Image) binding found or configured.")
        
        task.log("LollmsClient initialized for TTI.")
        task.set_progress(20)
        task.set_description("Generating image...")

        image_bytes = lc.tti.generate_image(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            **generation_params
        )
        task.log("Image data received from binding.")
        task.set_progress(80)
        task.set_description("Processing and saving image...")

        if not image_bytes:
            raise Exception("TTI binding returned empty image data.")

        b64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        discussion = get_user_discussion(username, discussion_id)
        if not discussion:
            raise Exception("Discussion not found after image generation.")

        with task.db_session_factory() as db:
            user_db = db.query(DBUser).filter(DBUser.username == username).first()
            db_pers = db.query(DBPersonality).filter(DBPersonality.id == user_db.active_personality_id).first() if user_db and user_db.active_personality_id else None

        sender_name = "lollms_tti"
        if db_pers:
            sender_name = db_pers.name

        new_message = discussion.add_message(
            sender=sender_name,
            content=f"Here is the generated image for the prompt:\n```\n{prompt}\n```",
            sender_type="assistant",
            images=[b64_image],
            parent_id=parent_message_id
        )
        discussion.commit()
        
        serialized_message = {
            "id": new_message.id,
            "sender": new_message.sender,
            "sender_type": new_message.sender_type,
            "content": new_message.content,
            "parent_message_id": new_message.parent_id,
            "binding_name": new_message.binding_name,
            "model_name": new_message.model_name,
            "token_count": new_message.tokens,
            "metadata": new_message.metadata,
            "image_references": [f"data:image/png;base64,{img}" for img in new_message.images or []],
            "created_at": new_message.created_at.isoformat() if new_message.created_at else datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "sources": (new_message.metadata or {}).get('sources', []),
            "events": (new_message.metadata or {}).get('events', [])
        }

        task.log("Image added to a new message and saved.")
        task.set_progress(100)
        
        return {
            "discussion_id": discussion_id,
            "status": "image_generated_in_message",
            "new_message": serialized_message
        }
    except Exception as e:
        task.log(f"Image generation failed: {e}", "ERROR")
        trace_exception(e)
        raise e

def _image_studio_generate_task(task: Task, username: str, request_data: dict):
    # ... (existing code remains the same)
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
        
        effective_model_full_name = f"{tti_binding_alias}/{lc.tti.config.get('model_name')}"
        generation_params.pop('model', None)
        n_images = generation_params.pop('n', 1)
        size_str = generation_params.pop('size', "1024x1024")
        
        try:
            if isinstance(size_str, str) and 'x' in size_str:
                width_str, height_str = size_str.split('x')
                generation_params["width"] = int(width_str)
                generation_params["height"] = int(height_str)
            elif "width" not in generation_params or "height" not in generation_params:
                generation_params["width"] = 1024
                generation_params["height"] = 1024
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
            
            if not image_bytes:
                task.log(f"Image {i+1} generation failed (empty response).", "ERROR")
                continue

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
    # ... (existing code remains the same)
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
            prompt=request_data.get('prompt'),
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

def _image_studio_enhance_prompt_task(task: Task, username: str, request_data: dict):
    # ... (existing code remains the same)
    task.log("Starting prompt enhancement task...")
    task.set_progress(5)
    
    request = ImagePromptEnhancementRequest(**request_data)

    try:
        with task.db_session_factory() as db:
            user_db = db.query(DBUser).filter(DBUser.username == username).first()
            if not user_db:
                raise Exception("User not found")
            model_full_name = request.model or user_db.lollms_model_name

        if not model_full_name or '/' not in model_full_name:
            lc = build_lollms_client_from_params(username)
        else:
            binding_alias, model_name = model_full_name.split('/', 1)
            lc = build_lollms_client_from_params(username=username, binding_alias=binding_alias, model_name=model_name)

        task.log("LLM client initialized.")
        task.set_progress(20)

        if request.mode == "update":
            system_prompt = "You are an expert image editing assistant. Your task is to translate a user's editing instructions into a concise, descriptive prompt that an AI image editing model (like InstructPix2Pix) can understand."
            system_prompt += "\n- The user will provide a base prompt and instructions for changes."
            if request.image_b64s:
                system_prompt += "\n- The user has also provided one or more images for context. Your instructions should apply to them."
            system_prompt += "\n- Generate a new 'prompt' that describes the desired edit. For example, if the user says 'make his shirt red', the new prompt should be 'make the shirt red'."
            system_prompt += "\n- If the user provides instructions to combine elements from multiple images, describe the final composite image."
            system_prompt += "\n- Do NOT generate a negative prompt unless explicitly asked."
            system_prompt += '\n- Respond ONLY with a single valid JSON object containing the "prompt" key. Do not add any extra text or explanations.'

            user_prompt_parts = [f'Base Prompt: "{request.prompt}"']
            if request.instructions and request.instructions.strip():
                 user_prompt_parts.append(f'Editing Instructions: "{request.instructions.strip()}"')
            else:
                 raise Exception("Editing instructions are required for 'update' mode.")
            user_prompt = "\n".join(user_prompt_parts)
        else:  # "description" mode
            system_prompt = "You are an expert image generation prompt engineer.\n"
            if request.instructions and request.instructions.strip():
                system_prompt += f"- Follow these user instructions when enhancing: {request.instructions.strip()}\n"

            if request.target in ['prompt', 'both']:
                system_prompt += "- Enhance the positive prompt by adding descriptive details, cinematic keywords, and stylistic elements to create a rich, detailed prompt for a text-to-image AI."
            if request.target in ['negative_prompt', 'both']:
                system_prompt += "\n- Enhance the negative prompt by adding common keywords to prevent artifacts and low quality."
            
            system_prompt += '\n- Respond ONLY with a single valid JSON object containing the key(s) for the prompt(s) you enhanced ("prompt", "negative_prompt"). Do not add any extra text or explanations.'

            user_prompt_parts = []
            if request.target in ['prompt', 'both']:
                user_prompt_parts.append(f'Positive: "{request.prompt}"')
            if request.target in ['negative_prompt', 'both']:
                user_prompt_parts.append(f'Negative: "{request.negative_prompt}"')
            user_prompt = "Enhance the following prompts:\n" + "\n".join(user_prompt_parts)

        task.set_progress(50)
        task.set_description("Generating enhanced prompt with AI...")

        if request.image_b64s:
            cleaned_images = [b64.split(',')[-1] for b64 in request.image_b64s]
            if hasattr(lc, 'generate_with_images'):
                raw_response = lc.generate_with_images(user_prompt, cleaned_images, system_prompt=system_prompt, max_generation_size=2048)
            elif hasattr(lc, 'binding') and hasattr(lc.binding, 'generate_with_images'):
                raw_response = lc.binding.generate_with_images(user_prompt, cleaned_images, system_prompt=system_prompt, max_generation_size=2048)
            else:
                task.log("Vision generation method not found on client. Falling back to text-only enhancement.", "WARNING")
                raw_response = lc.generate_text(user_prompt, system_prompt=system_prompt, stream=False, max_generation_size=2048)
        else:
            raw_response = lc.generate_text(user_prompt, system_prompt=system_prompt, stream=False, max_generation_size=2048)
        
        task.log("AI response received.")
        task.set_progress(80)

        json_match = raw_response[raw_response.find('{'):raw_response.rfind('}') + 1]
        if not json_match:
            if request.mode == 'description' and request.target == 'prompt':
                 task.log("AI did not return valid JSON. Treating response as prompt.", "WARNING")
                 response_data = {'prompt': raw_response.strip()}
            else:
                 raise Exception("AI did not return a valid JSON object.")
        else:
            try:
                enhanced_data = json.loads(json_match)
                response_data = {}
                if 'prompt' in enhanced_data: response_data['prompt'] = enhanced_data.get('prompt')
                if 'negative_prompt' in enhanced_data: response_data['negative_prompt'] = enhanced_data.get('negative_prompt')
            except json.JSONDecodeError:
                 raise Exception("Failed to decode AI response as JSON.")

        task.log("Prompt enhanced successfully.")
        task.set_progress(100)
        return response_data
        
    except Exception as e:
        task.log(f"Prompt enhancement failed: {e}", "ERROR")
        trace_exception(e)
        raise e

# --- New Timelapse Task ---
def _generate_timelapse_task(task: Task, username: str, request_data: dict):
    task.log("Starting timelapse generation...")
    task.set_progress(5)
    
    if not MOVIEPY_AVAILABLE:
        task.log("MoviePy not installed. Creating video might fail or fallback to raw images.", "WARNING")

    try:
        request = TimelapseRequest(**request_data)
        
        with task.db_session_factory() as db:
            user = db.query(DBUser).filter(DBUser.username == username).first()
            if not user:
                raise Exception("User not found.")
            
            # Setup TTI Client
            model_full_name = request.model or user.tti_binding_model_name
            tti_binding_alias = None
            tti_model_name = None
            if model_full_name and '/' in model_full_name:
                tti_binding_alias, tti_model_name = model_full_name.split('/', 1)
            else:
                default_tti_binding = db.query(DBTTIBinding).filter(DBTTIBinding.is_active == True).order_by(DBTTIBinding.id).first()
                if default_tti_binding:
                    tti_binding_alias = default_tti_binding.alias
                else:
                    raise Exception("No active TTI binding found.")

        lc = build_lollms_client_from_params(
            username=username,
            tti_binding_alias=tti_binding_alias,
            tti_model_name=tti_model_name
        )
        if not lc.tti:
            raise Exception("TTI binding not available.")

        user_images_path = get_user_images_path(username)
        generated_files = []
        
        # 1. Generate Frames
        total_frames = len(request.keyframes)
        for i, keyframe in enumerate(request.keyframes):
            if task.cancellation_event.is_set():
                break
                
            task.log(f"Generating keyframe {i+1}/{total_frames}: {keyframe.prompt[:30]}...")
            task.set_progress(5 + int(50 * (i / total_frames)))
            
            image_bytes = lc.tti.generate_image(
                prompt=keyframe.prompt,
                negative_prompt=request.negative_prompt,
                width=request.width,
                height=request.height,
                seed=request.seed
            )
            
            if image_bytes:
                filename = f"{uuid.uuid4().hex}.png"
                file_path = user_images_path / filename
                with open(file_path, "wb") as f:
                    f.write(image_bytes)
                generated_files.append({"path": file_path, "duration": keyframe.duration})
            else:
                task.log(f"Failed to generate keyframe {i+1}", "ERROR")

        if not generated_files:
            raise Exception("No images generated for timelapse.")

        # 2. Build Video
        task.log("Compiling video...")
        task.set_progress(60)
        
        video_filename = f"timelapse_{uuid.uuid4().hex}.mp4"
        video_path = user_images_path / video_filename
        
        if MOVIEPY_AVAILABLE:
            clips = []
            for item in generated_files:
                clip = ImageClip(str(item["path"])).set_duration(item["duration"])
                clips.append(clip)
            
            if len(clips) > 1 and request.transition_duration > 0:
                # Simple crossfade logic
                # For basic concat with transition:
                # moviepy's concatenate_videoclips with method="compose" handles overlap but needs offsets
                # Easier: Manually compositing with set_start and crossfadein
                
                final_clips = [clips[0]]
                start_time = clips[0].duration - request.transition_duration
                
                for i in range(1, len(clips)):
                    prev = clips[i-1]
                    curr = clips[i].set_start(start_time).crossfadein(request.transition_duration)
                    final_clips.append(curr)
                    start_time += (curr.duration - request.transition_duration)
                
                video = CompositeVideoClip(final_clips)
                video.write_videofile(str(video_path), fps=request.fps, codec="libx264", audio=False)
            else:
                video = concatenate_videoclips(clips, method="compose")
                video.write_videofile(str(video_path), fps=request.fps, codec="libx264", audio=False)
        else:
            task.log("MoviePy unavailable. Skipping video creation. Images are saved.", "WARNING")
            # Fallback: Just return the images as a result list
            pass

        task.set_progress(100)
        
        if video_path.exists():
            return {
                "video_url": f"/api/image-studio/{video_filename}/file",
                "filename": video_filename,
                "type": "video"
            }
        else:
            return {
                "images": [f"/api/image-studio/{Path(f['path']).name}/file" for f in generated_files],
                "type": "image_sequence"
            }

    except Exception as e:
        task.log(f"Timelapse generation failed: {e}", "ERROR")
        trace_exception(e)
        raise e
