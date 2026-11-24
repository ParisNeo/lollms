
import datetime
import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

import yaml
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.db.models.skill import Skill as DBSkill
from backend.db.models.user import User as DBUser
from backend.models.personality import PersonalitySendRequest
from backend.models.user import UserAuthDetails
from backend.session import get_current_active_user

skills_router = APIRouter(
    prefix="/api/skills",
    tags=["Skills"],
    dependencies=[Depends(get_current_active_user)]
)

MAX_SKILL_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_SUPPORTING_FILES = 64
MAX_SUPPORTING_FILE_BYTES = 1024 * 1024
RESERVED_PACKAGE_FILES = {"skill.md"}
FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)(.*)\Z", re.DOTALL)


class SkillBase(BaseModel):
    name: str
    content: str
    description: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = "markdown"
    author: Optional[str] = None
    version: Optional[str] = "1.0.0"
    supporting_files: Dict[str, str] = Field(default_factory=dict)


class SkillCreate(SkillBase):
    is_system: bool = False


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None
    author: Optional[str] = None
    version: Optional[str] = None
    is_system: Optional[bool] = None
    supporting_files: Optional[Dict[str, str]] = None


class SkillPublic(SkillBase):
    id: str
    is_system: bool = False
    owner_user_id: Optional[int] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True


class ExportFormat(BaseModel):
    format: str


def _required_metadata_value(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"SKILL.md YAML frontmatter requires a non-empty '{field_name}'.")
    return value.strip()


def _split_skill_markdown(text: str, require_metadata: bool = False) -> Tuple[Dict[str, Any], str]:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    match = FRONTMATTER_RE.match(normalized)
    if not match:
        if require_metadata or normalized.lstrip().startswith("---"):
            raise ValueError(
                "SKILL.md must start with valid YAML frontmatter containing name, author, and description."
            )
        return {}, normalized.strip()

    metadata = yaml.safe_load(match.group(1))
    if not isinstance(metadata, dict):
        raise ValueError("SKILL.md YAML frontmatter must be a mapping.")
    if require_metadata:
        for field_name in ("name", "author", "description"):
            _required_metadata_value(metadata.get(field_name), field_name)
    return metadata, match.group(2).strip()


def _build_skill_markdown(
    content: str,
    name: Optional[str],
    author: Optional[str],
    description: Optional[str],
    category: Optional[str],
    version: Optional[str],
    language: Optional[str],
) -> Tuple[str, Dict[str, str]]:
    metadata, body = _split_skill_markdown(content)
    resolved = {
        "name": _required_metadata_value(name if name is not None else metadata.get("name"), "name"),
        "author": _required_metadata_value(author if author is not None else metadata.get("author"), "author"),
        "description": _required_metadata_value(
            description if description is not None else metadata.get("description"), "description"
        ),
    }
    frontmatter = dict(metadata)
    frontmatter.update(resolved)
    optional_values = {"category": category, "version": version, "language": language}
    for key, value in optional_values.items():
        if value:
            frontmatter[key] = value
    yaml_header = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{yaml_header}\n---\n\n{body}\n", resolved


def _normalize_supporting_files(files: Optional[Dict[str, str]]) -> Dict[str, str]:
    if files is None:
        return {}
    if not isinstance(files, dict):
        raise ValueError("supporting_files must be a mapping of relative paths to UTF-8 text.")
    if len(files) > MAX_SUPPORTING_FILES:
        raise ValueError(f"A skill can contain at most {MAX_SUPPORTING_FILES} supporting files.")

    normalized_files: Dict[str, str] = {}
    for raw_path, content in files.items():
        if not isinstance(raw_path, str) or not isinstance(content, str):
            raise ValueError("Supporting file paths and contents must be strings.")
        path = raw_path.strip().replace("\\", "/")
        pure_path = PurePosixPath(path)
        if (
            not path
            or path.startswith("/")
            or pure_path.is_absolute()
            or any(part in ("", ".", "..") for part in pure_path.parts)
            or re.match(r"^[A-Za-z]:", path)
        ):
            raise ValueError(f"Unsafe supporting file path: '{raw_path}'.")
        normalized_path = pure_path.as_posix()
        if normalized_path.lower() in RESERVED_PACKAGE_FILES:
            raise ValueError("SKILL.md is the main skill file and cannot be a supporting file.")
        if normalized_path in normalized_files:
            raise ValueError(f"Duplicate supporting file: '{normalized_path}'.")
        if len(content.encode("utf-8")) > MAX_SUPPORTING_FILE_BYTES:
            raise ValueError(f"Supporting file '{normalized_path}' exceeds the 1 MiB limit.")
        normalized_files[normalized_path] = content
    return normalized_files


def _to_skill_public(skill: DBSkill) -> SkillPublic:
    return SkillPublic(
        id=skill.id,
        name=skill.name,
        description=skill.description,
        category=skill.category or "Development",
        language=skill.language or "markdown",
        content=skill.content,
        author=skill.author or ("System" if skill.owner_user_id is None else "Personal"),
        version=skill.version or "1.0.0",
        supporting_files=skill.supporting_files or {},
        is_system=(skill.owner_user_id is None),
        owner_user_id=skill.owner_user_id,
        created_at=skill.created_at,
        updated_at=skill.updated_at
    )


def _http_validation_error(error: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))


def _find_owned_skill(db: Session, skill_id: str, current_user: UserAuthDetails) -> DBSkill:
    skill = db.query(DBSkill).filter(
        DBSkill.id == skill_id,
        or_(DBSkill.owner_user_id == current_user.id, DBSkill.owner_user_id.is_(None))
    ).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill


def _export_markdown(skill: DBSkill) -> str:
    try:
        markdown, _ = _build_skill_markdown(
            skill.content,
            skill.name,
            skill.author or "Community",
            skill.description,
            skill.category,
            skill.version,
            skill.language,
        )
        return markdown
    except ValueError as error:
        raise _http_validation_error(error)


@skills_router.get("", response_model=List[SkillPublic])
def get_skills(current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    skills = db.query(DBSkill).filter(
        or_(DBSkill.owner_user_id == current_user.id, DBSkill.owner_user_id.is_(None))
    ).order_by(DBSkill.name).all()
    return [_to_skill_public(skill) for skill in skills]


@skills_router.post("", response_model=SkillPublic, status_code=status.HTTP_201_CREATED)
def create_skill(
    skill: SkillCreate,
    overwrite: bool = Query(True),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    is_admin = getattr(current_user, "is_admin", False)
    target_owner_id = None if (is_admin and skill.is_system) else current_user.id
    target_author = skill.author or ("System" if target_owner_id is None else current_user.username)

    try:
        content, metadata = _build_skill_markdown(
            skill.content, skill.name, target_author, skill.description,
            skill.category, skill.version, skill.language
        )
        supporting_files = _normalize_supporting_files(skill.supporting_files)
    except ValueError as error:
        raise _http_validation_error(error)

    if overwrite:
        existing_skill = db.query(DBSkill).filter(
            DBSkill.owner_user_id == target_owner_id,
            DBSkill.name == metadata["name"]
        ).first()
        if existing_skill:
            existing_skill.content = content
            existing_skill.description = metadata["description"]
            existing_skill.category = skill.category
            existing_skill.language = skill.language
            existing_skill.author = metadata["author"]
            existing_skill.version = skill.version or existing_skill.version
            existing_skill.supporting_files = supporting_files
            existing_skill.updated_at = datetime.datetime.now(datetime.timezone.utc)
            db.commit()
            db.refresh(existing_skill)
            return _to_skill_public(existing_skill)

    new_skill = DBSkill(
        name=metadata["name"],
        content=content,
        description=metadata["description"],
        category=skill.category,
        language=skill.language,
        author=metadata["author"],
        version=skill.version or "1.0.0",
        supporting_files=supporting_files,
        owner_user_id=target_owner_id
    )
    db.add(new_skill)
    try:
        db.commit()
        db.refresh(new_skill)
        return _to_skill_public(new_skill)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error creating skill.")


@skills_router.put("/{skill_id}", response_model=SkillPublic)
def update_skill(skill_id: str, skill_update: SkillUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    skill = db.query(DBSkill).filter(DBSkill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    is_admin = getattr(current_user, "is_admin", False)
    is_system = skill.owner_user_id is None
    if is_system and not is_admin:
        raise HTTPException(status_code=403, detail="Only administrators can edit System Skills.")
    if not is_system and skill.owner_user_id != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail="You do not have permission to edit this skill.")

    update_data = skill_update.model_dump(exclude_unset=True)
    requested_system = update_data.pop("is_system", None)
    if requested_system is not None and is_admin:
        skill.owner_user_id = None if requested_system else current_user.id

    try:
        content, metadata = _build_skill_markdown(
            update_data.pop("content", skill.content),
            update_data.pop("name", skill.name),
            update_data.pop("author", skill.author),
            update_data.pop("description", skill.description),
            update_data.get("category", skill.category),
            update_data.get("version", skill.version),
            update_data.get("language", skill.language),
        )
        if "supporting_files" in update_data:
            skill.supporting_files = _normalize_supporting_files(update_data.pop("supporting_files"))
    except ValueError as error:
        raise _http_validation_error(error)

    skill.name = metadata["name"]
    skill.author = metadata["author"]
    skill.description = metadata["description"]
    skill.content = content
    for key, value in update_data.items():
        if hasattr(skill, key):
            setattr(skill, key, value)

    try:
        db.commit()
        db.refresh(skill)
        return _to_skill_public(skill)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error updating skill.")


@skills_router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(skill_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    skill = db.query(DBSkill).filter(DBSkill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    is_admin = getattr(current_user, "is_admin", False)
    is_system = skill.owner_user_id is None
    is_authorized = is_admin or (not is_system and skill.owner_user_id == current_user.id)
    if not is_authorized:
        detail_msg = "Only administrators can delete System Skills." if is_system else "You do not have permission to delete this skill."
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail_msg)

    db.delete(skill)
    db.commit()


@skills_router.post("/{skill_id}/export")
def export_skill(skill_id: str, payload: ExportFormat, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    skill = _find_owned_skill(db, skill_id, current_user)
    safe_name = re.sub(r'[^\w\-_\. ]', '_', skill.name)
    req_format = (payload.format or '').lower().strip()

    if req_format in ("zip", "package"):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("SKILL.md", _export_markdown(skill))
            for path, content in sorted((skill.supporting_files or {}).items()):
                archive.writestr(path, content)
        return Response(
            content=output.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="skill_{safe_name}.zip"'}
        )

    if req_format == 'xml':
        root = ET.Element("skill", id=skill.id)
        ET.SubElement(root, "name").text = skill.name
        if skill.description:
            ET.SubElement(root, "description").text = skill.description
        if skill.category:
            ET.SubElement(root, "category").text = skill.category
        if skill.language:
            ET.SubElement(root, "language").text = skill.language
        if skill.author:
            ET.SubElement(root, "author").text = skill.author
        if skill.version:
            ET.SubElement(root, "version").text = str(skill.version)
        ET.SubElement(root, "timestamp").text = str(int(skill.updated_at.timestamp() * 1000)) if skill.updated_at else "0"
        content_el = ET.SubElement(root, "content")
        content_el.text = f"<![CDATA[\n{skill.content}\n]]>"
        xml_str = ET.tostring(root, encoding="utf-8").decode("utf-8")
        xml_str = xml_str.replace("&lt;![CDATA[", "<![CDATA[").replace("]]&gt;", "]]>")
        return Response(content=xml_str, media_type="application/xml", headers={"Content-Disposition": f'attachment; filename="skill_{safe_name}.xml"'})

    if req_format in ('claude', 'md', 'markdown'):
        return Response(
            content=_export_markdown(skill),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="skill_{safe_name}.md"'}
        )
    raise HTTPException(status_code=400, detail="Unsupported format. Use 'zip', 'xml', 'md', or 'claude'.")


@skills_router.post("/{skill_id}/share", status_code=status.HTTP_200_OK)
async def share_skill(
    skill_id: str,
    payload: PersonalitySendRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    skill = db.query(DBSkill).filter(DBSkill.id == skill_id, DBSkill.owner_user_id == current_user.id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    target_user = db.query(DBUser).filter(DBUser.username == payload.target_username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")
    if db.query(DBSkill).filter(DBSkill.owner_user_id == target_user.id, DBSkill.name == skill.name).first():
        raise HTTPException(status_code=409, detail=f"User already has a skill named '{skill.name}'")

    share_log = f"\n[Shared with {target_user.username} on {datetime.datetime.now().strftime('%Y-%m-%d')}]"
    if not skill.description:
        skill.description = share_log
    elif share_log not in skill.description:
        skill.description += f" {share_log}"

    new_skill = DBSkill(
        name=skill.name,
        description=skill.description,
        category=skill.category,
        language=skill.language,
        content=skill.content,
        supporting_files=skill.supporting_files or {},
        author=f"Shared by {current_user.username}",
        owner_user_id=target_user.id
    )
    db.add(new_skill)
    try:
        db.commit()
        from backend.ws_manager import manager
        manager.send_personal_message_sync({
            "type": "skill_shared",
            "data": {
                "message": f"🎁 {current_user.username} shared AI skill: {skill.name}",
                "sender_username": current_user.username,
                "sender_icon": current_user.icon,
                "skill_id": new_skill.id,
                "title": skill.name,
                "type": "success",
                "duration": 6000
            }
        }, target_user.id)
        manager.send_personal_message_sync({"type": "skill_saved", "data": {"title": skill.name}}, target_user.id)
        return {"message": f"Skill shared with {payload.target_username}"}
    except Exception as error:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(error))


def _decode_utf8(data: bytes, path: str) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError(f"'{path}' must be a UTF-8 text file.")


def _parse_zip_skill(content_bytes: bytes) -> Dict[str, Any]:
    entries: List[Tuple[str, bytes]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(content_bytes)) as archive:
            if len(archive.infolist()) > MAX_SUPPORTING_FILES + 16:
                raise ValueError("The skill archive contains too many files.")
            total_size = 0
            for info in archive.infolist():
                if info.is_dir():
                    continue
                total_size += info.file_size
                if total_size > MAX_SKILL_UPLOAD_BYTES:
                    raise ValueError("The uncompressed skill package exceeds the 10 MiB limit.")
                path = info.filename.replace("\\", "/")
                if "__MACOSX" in PurePosixPath(path).parts:
                    continue
                entries.append((path, archive.read(info)))
    except zipfile.BadZipFile:
        raise ValueError("Invalid ZIP skill package.")

    root_candidates = [path for path, _ in entries if path.lower() == "skill.md"]
    if not root_candidates:
        top_levels = {PurePosixPath(path).parts[0] for path, _ in entries if PurePosixPath(path).parts}
        if len(top_levels) == 1:
            prefix = f"{next(iter(top_levels))}/"
            root_candidates = [path for path, _ in entries if path.lower() == f"{prefix}skill.md"]
    if len(root_candidates) != 1:
        raise ValueError("The ZIP package must contain one root SKILL.md (optionally inside one top-level folder).")

    main_path = root_candidates[0]
    base_prefix = main_path[:-len("SKILL.md")]
    supporting_files: Dict[str, str] = {}
    main_content = ""
    for path, data in entries:
        if not path.startswith(base_prefix):
            raise ValueError("The ZIP package cannot contain files outside the skill root folder.")
        relative_path = path[len(base_prefix):]
        if relative_path.lower() == "skill.md":
            main_content = _decode_utf8(data, "SKILL.md")
            continue
        text = _decode_utf8(data, relative_path)
        supporting_files[relative_path] = text

    metadata, _ = _split_skill_markdown(main_content, require_metadata=True)
    return {
        "name": metadata["name"].strip(),
        "description": metadata["description"].strip(),
        "author": metadata["author"].strip(),
        "category": str(metadata.get("category") or "Imported"),
        "language": str(metadata.get("language") or "markdown"),
        "version": str(metadata.get("version") or "1.0.0"),
        "content": main_content,
        "supporting_files": _normalize_supporting_files(supporting_files),
    }


def _parse_text_skill(text_content: str, current_user: UserAuthDetails) -> Dict[str, Any]:
    if "<!DOCTYPE" in text_content.upper() or "<!ENTITY" in text_content.upper():
        raise ValueError("XML DTD and custom entity declarations are forbidden.")
    if text_content.strip().startswith("---"):
        metadata, _ = _split_skill_markdown(text_content, require_metadata=True)
        return {
            "name": metadata["name"].strip(),
            "description": metadata["description"].strip(),
            "author": metadata["author"].strip(),
            "category": str(metadata.get("category") or "Imported"),
            "language": str(metadata.get("language") or "markdown"),
            "version": str(metadata.get("version") or "1.0.0"),
            "content": text_content,
            "supporting_files": {},
        }
    if "<skill" not in text_content:
        raise ValueError("Unknown format. Upload SKILL.md, skill XML, or a ZIP skill package.")

    cdata_match = re.search(r'<!\[CDATA\[(.*?)\]\]>', text_content, re.DOTALL)
    cdata_content = cdata_match.group(1) if cdata_match else ""
    clean_xml = re.sub(r'<!\[CDATA\[.*?\]\]>', '', text_content, flags=re.DOTALL)
    root = ET.fromstring(clean_xml)

    def element_text(tag: str, default: str = "") -> str:
        element = root.find(tag)
        return element.text if element is not None and element.text else default

    content_element = root.find("content")
    skill_content = cdata_content.strip() if cdata_content else (
        content_element.text.strip() if content_element is not None and content_element.text else ""
    )
    return {
        "name": element_text("name", "Imported Skill"),
        "description": element_text("description"),
        "author": element_text("author", current_user.username),
        "category": element_text("category", "Imported"),
        "language": element_text("language", "markdown"),
        "version": element_text("version", "1.0.0"),
        "content": skill_content,
        "supporting_files": {},
    }


@skills_router.post("/import", response_model=SkillPublic)
async def import_skill(file: UploadFile = File(...), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)):
    content_bytes = await file.read(MAX_SKILL_UPLOAD_BYTES + 1)
    if len(content_bytes) > MAX_SKILL_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Skill upload exceeds the 10 MiB limit.")

    try:
        if zipfile.is_zipfile(io.BytesIO(content_bytes)):
            imported = _parse_zip_skill(content_bytes)
        else:
            imported = _parse_text_skill(_decode_utf8(content_bytes, file.filename or "skill"), current_user)

        content, metadata = _build_skill_markdown(
            imported["content"], imported["name"], imported["author"], imported["description"],
            imported["category"], imported["version"], imported["language"]
        )
        new_skill = DBSkill(
            name=metadata["name"],
            content=content,
            description=metadata["description"],
            category=imported["category"],
            language=imported["language"],
            author=metadata["author"],
            version=imported["version"],
            supporting_files=imported["supporting_files"],
            owner_user_id=current_user.id
        )
        db.add(new_skill)
        db.commit()
        db.refresh(new_skill)
        return _to_skill_public(new_skill)
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to import skill: {error}")
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A skill with this name already exists.")
    except ET.ParseError as error:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to import skill: invalid XML: {error}")
