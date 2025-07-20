import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from backend.config import LOCALS_DIR




languages_router = APIRouter(prefix="/api/languages", tags=["Languages router"])

@languages_router.get("/", response_class=JSONResponse)
async def get_languages():
    languages_dict = {}
    if not LOCALS_DIR.is_dir():
        print(f"Warning: Locals directory not found at {LOCALS_DIR}")
        # Return the expected array format even for the fallback
        return [{"value": "en", "label": "English"}, {"value": "fr", "label": "Français"}]

    try:
        for filepath in LOCALS_DIR.glob("*.json"):
            lang_code = filepath.stem
            display_name = lang_code.upper()
            if lang_code == "en": display_name = "English"
            elif lang_code == "fr": display_name = "Français"
            elif lang_code == "es": display_name = "Español"
            elif lang_code == "de": display_name = "Deutsch"
            languages_dict[lang_code] = display_name
    except Exception as e:
        print(f"Error scanning locals directory: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve language list.")

    if not languages_dict:
        print(f"Warning: No JSON language files found in {LOCALS_DIR}")
        # Return the expected array format even for the fallback
        return [{"value": "en", "label": "English"}]
    
    # --- THIS IS THE FIX ---
    # Transform the dictionary into the array of objects the frontend expects
    languages_list = [{"value": code, "label": name} for code, name in languages_dict.items()]
    
    # Sort the list alphabetically by label for a better user experience
    languages_list.sort(key=lambda x: x['label'])
    
    return languages_list


@languages_router.get("/locals/{lang_code}.json")
async def get_locale_file(lang_code: str):
    if not LOCALS_DIR.is_dir():
        raise HTTPException(status_code=404, detail=f"Locals directory not found.")

    if not lang_code.replace('-', '').isalnum():
        raise HTTPException(status_code=400, detail="Invalid language code format.")

    file_path = LOCALS_DIR / f"{lang_code}.json"

    if not file_path.is_file():
        base_lang_code = lang_code.split('-')[0]
        if base_lang_code != lang_code:
            base_file_path = LOCALS_DIR / f"{base_lang_code}.json"
            if base_file_path.is_file():
                print(f"Serving base language file {base_file_path} for requested {file_path}")
                try:
                    with open(base_file_path, "r", encoding="utf-8") as f: content = json.load(f)
                    return JSONResponse(content=content)
                except Exception as e:
                    print(f"Error reading base locale file {base_file_path}: {e}")
                    raise HTTPException(status_code=500, detail="Error reading locale file.")
        raise HTTPException(status_code=404, detail=f"Locale file for '{lang_code}' not found.")

    try:
        with open(file_path, "r", encoding="utf-8") as f: content = json.load(f)
        return JSONResponse(content=content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Locale file '{lang_code}.json' is not valid JSON.")
    except Exception as e:
        print(f"Error reading locale file {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Error reading locale file.")