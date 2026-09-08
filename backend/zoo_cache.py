import yaml
import json
import time
from pathlib import Path
import base64
from typing import List, Dict, Any, Literal, Optional
from sqlalchemy.orm import Session
from filelock import FileLock, Timeout

from backend.db import get_db
from backend.db.models.service import AppZooRepository, MCPZooRepository, PromptZooRepository, PersonalityZooRepository, SkillZooRepository
from backend.db.models.prompt import SavedPrompt
from backend.db.models.personality import Personality
from backend.db.models.skill import Skill as DBSkill
from backend.config import APPS_ZOO_ROOT_PATH, MCPS_ZOO_ROOT_PATH, PROMPTS_ZOO_ROOT_PATH, PERSONALITIES_ZOO_ROOT_PATH, SKILLS_ZOO_ROOT_PATH, APP_DATA_DIR
import datetime
from ascii_colors import ASCIIColors
import os
import re

ITEM_TYPES = Literal['app', 'mcp', 'prompt', 'personality', 'skill']
CACHE_FILE = APP_DATA_DIR / "zoo_cache.json"
CACHE_LOCK_FILE = APP_DATA_DIR / "zoo_cache.lock"
CACHE_LOCK_TIMEOUT = 5 # 5 seconds max timeout


_cache: Dict[str, Any] = {"timestamp": 0, "data": {}}

def _sanitize_for_json(data: Any) -> Any:
    """Recursively sanitizes data to ensure it's JSON serializable."""
    if isinstance(data, (datetime.datetime, datetime.date)):
        return data.isoformat()
    if isinstance(data, dict):
        return {k: _sanitize_for_json(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_sanitize_for_json(v) for v in data]
    return data

def get_zoo_root_path(item_type: ITEM_TYPES) -> Path:
    if item_type == 'app': return APPS_ZOO_ROOT_PATH
    if item_type == 'mcp': return MCPS_ZOO_ROOT_PATH
    if item_type == 'prompt': return PROMPTS_ZOO_ROOT_PATH
    if item_type == 'personality': return PERSONALITIES_ZOO_ROOT_PATH
    if item_type == 'skill': return SKILLS_ZOO_ROOT_PATH
    raise ValueError(f"Invalid item type: {item_type}")

def get_db_repo_model(item_type: ITEM_TYPES):
    if item_type == 'app': return AppZooRepository
    if item_type == 'mcp': return MCPZooRepository
    if item_type == 'prompt': return PromptZooRepository
    if item_type == 'personality': return PersonalityZooRepository
    if item_type == 'skill': return SkillZooRepository
    raise ValueError(f"Invalid item type: {item_type}")

def get_installed_items(db: Session, item_type: ITEM_TYPES) -> set:
    if item_type in ['app', 'mcp']:
        from backend.db.models.service import App as DBApp
        return {item.name for item in db.query(DBApp.name).filter(DBApp.is_installed == True, DBApp.app_metadata['item_type'].as_string() == item_type).all()}
    if item_type == 'prompt':
        return {item.name for item in db.query(SavedPrompt.name).filter(SavedPrompt.owner_user_id.is_(None)).all()}
    if item_type == 'personality':
        return {item.name for item in db.query(Personality.name).filter(Personality.owner_user_id.is_(None)).all()}
    if item_type == 'skill':
        return {item.name for item in db.query(DBSkill.name).all()}
    return set()

def _extract_license_from_path(item_path: Path, repo_path: Optional[Path] = None) -> Optional[str]:
    """Finds and identifies license information in a skill folder or repo."""
    lic_candidates = ["LICENSE", "LICENSE.txt", "LICENSE.md", "license", "license.txt", "license.md"]

    # Check item directory first
    if item_path.is_dir():
        for cand in lic_candidates:
            lic_file = item_path / cand
            if lic_file.is_file():
                try:
                    text = lic_file.read_text(encoding='utf-8', errors='replace').strip()
                    if text:
                        lines = [l.strip() for l in text.splitlines() if l.strip()]
                        if lines:
                            first_line = lines[0]
                            # Detect common licenses
                            for known in ["MIT", "Apache-2.0", "Apache 2.0", "GPL-3.0", "GPL", "BSD", "CC0", "Unlicense"]:
                                if known.lower() in text[:200].lower():
                                    return known
                            if len(first_line) <= 30 and not first_line.lower().startswith("copyright"):
                                return first_line
                            return "Standard License"
                except Exception:
                    pass

    # Check parent category or repo root
    if repo_path and repo_path.is_dir():
        for cand in lic_candidates:
            lic_file = repo_path / cand
            if lic_file.is_file():
                try:
                    text = lic_file.read_text(encoding='utf-8', errors='replace').strip()
                    for known in ["MIT", "Apache-2.0", "Apache 2.0", "GPL-3.0", "GPL", "BSD", "CC0", "Unlicense"]:
                        if known.lower() in text[:200].lower():
                            return known
                    return "Repository License"
                except Exception:
                    pass

    return None

def _parse_skill_metadata(item_path: Path, repo_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Parses metadata, content, and license for a skill from either:
    1. A folder containing description.yaml, SKILL.md, skill.md, or skill.xml
    2. A standalone .md or .xml skill file
    """
    metadata: Dict[str, Any] = {}
    content = ""
    raw_text = ""

    # Case 1: item_path is a directory
    if item_path.is_dir():
        # Check description.yaml
        for yaml_candidate in ["description.yaml", "description.yml", "DESCRIPTION.YAML"]:
            c_path = item_path / yaml_candidate
            if c_path.exists():
                try:
                    with open(c_path, 'r', encoding='utf-8') as f:
                        metadata = yaml.safe_load(f) or {}
                        break
                except Exception:
                    pass

        # Check for skill content files (case-insensitive search)
        skill_file = None
        for cand in ["SKILL.md", "skill.md", "Skill.md", "skill.xml", "SKILL.XML", "Skill.xml"]:
            if (item_path / cand).exists():
                skill_file = item_path / cand
                break

        if not skill_file:
            # Check for any .xml or .md excluding readmes & licenses
            for f in item_path.iterdir():
                f_name_lower = f.name.lower()
                if f.is_file() and f_name_lower not in ["readme.md", "license", "license.txt", "license.md", "contributing.md", "description.yaml", "description.yml"]:
                    if f.suffix.lower() in [".md", ".xml"]:
                        skill_file = f
                        break

        if skill_file and skill_file.exists():
            try:
                raw_text = skill_file.read_text(encoding='utf-8', errors='replace')
                content = raw_text
            except Exception as e:
                print(f"Warning: Could not read skill file at {skill_file}: {e}")

    # Case 2: item_path is a standalone file (.md or .xml)
    elif item_path.is_file():
        try:
            raw_text = item_path.read_text(encoding='utf-8', errors='replace')
            content = raw_text
        except Exception as e:
            print(f"Warning: Could not read standalone skill file {item_path}: {e}")

    # Parse metadata out of markdown frontmatter (--- ... ---)
    if raw_text.strip().startswith("---"):
        try:
            parts = re.split(r'^---[ \t]*$', raw_text.replace('\r\n', '\n'), maxsplit=2, flags=re.MULTILINE)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                if isinstance(frontmatter, dict):
                    for k, v in frontmatter.items():
                        if not metadata.get(k):
                            metadata[k] = v
                content = parts[2].strip()
        except Exception:
            pass

    # Parse metadata out of XML tags if present
    if "<skill" in raw_text.lower():
        m_name = re.search(r'<name>(.*?)</name>', raw_text, re.IGNORECASE | re.DOTALL) or re.search(r'name=["\'](.*?)["\']', raw_text)
        if m_name and not metadata.get('name'):
            metadata['name'] = m_name.group(1).strip()

        m_desc = re.search(r'<description>(.*?)</description>', raw_text, re.IGNORECASE | re.DOTALL) or re.search(r'description=["\'](.*?)["\']', raw_text)
        if m_desc and not metadata.get('description'):
            metadata['description'] = m_desc.group(1).strip()

        m_cat = re.search(r'<category>(.*?)</category>', raw_text, re.IGNORECASE | re.DOTALL)
        if m_cat and not metadata.get('category'):
            metadata['category'] = m_cat.group(1).strip()

    # Markdown # Title heuristic if name is still missing
    if not metadata.get('name') and raw_text:
        m_head = re.search(r'^#\s+(.+)$', raw_text, re.MULTILINE)
        if m_head:
            metadata['name'] = m_head.group(1).strip()

    # Heuristic for description if still missing
    if not metadata.get('description') and raw_text:
        text_lines = [
            l.strip() for l in raw_text.splitlines() 
            if l.strip() and not l.strip().startswith(('#', '---', '<', '```'))
        ]
        if text_lines:
            metadata['description'] = text_lines[0][:220]

    # Category heuristic: infer from directory hierarchy (e.g. repo/Category/SkillFolder/SKILL.md)
    if not metadata.get('category') and repo_path:
        try:
            rel_parts = item_path.relative_to(repo_path).parts
            if len(rel_parts) > 1:
                metadata['category'] = rel_parts[0].replace('_', ' ').replace('-', ' ').title()
        except Exception:
            pass

    # Extract license
    detected_license = _extract_license_from_path(item_path, repo_path=repo_path)
    if detected_license:
        metadata['license'] = detected_license

    # Safe defaults
    base_name = item_path.stem if item_path.is_file() else item_path.name
    if not metadata.get('name'):
        metadata['name'] = base_name.replace('_', ' ').replace('-', ' ').title()

    if not metadata.get('category'):
        metadata['category'] = 'Development'

    if not metadata.get('description'):
        metadata['description'] = f"AI skill for {metadata['name']}"

    if not metadata.get('version'):
        metadata['version'] = '1.0.0'

    if not metadata.get('author'):
        metadata['author'] = 'Community'

    metadata['content'] = content or raw_text
    return metadata

def parse_item_metadata(item_path: Path, item_type: ITEM_TYPES, repo_path: Optional[Path] = None) -> Dict[str, Any]:
    metadata = {}
    if item_type == 'personality':
        desc_path = item_path / "description.yaml"
        conf_path = item_path / "config.yaml"
        if desc_path.exists():
            with open(desc_path, 'r', encoding='utf-8') as f:
                metadata = yaml.safe_load(f) or {}
            if 'description' not in metadata and 'personality_description' in metadata:
                metadata['description'] = metadata['personality_description']
            if 'prompt_text' not in metadata and 'personality_conditioning' in metadata:
                metadata['prompt_text'] = metadata['personality_conditioning']
        elif conf_path.exists():
            with open(conf_path, 'r', encoding='utf-8') as f:
                legacy_data = yaml.safe_load(f) or {}
            metadata = {
                'name': legacy_data.get('name'), 'version': str(legacy_data.get('version', 'N/A')),
                'author': legacy_data.get('author'), 'category': legacy_data.get('category'),
                'description': legacy_data.get('personality_description') or legacy_data.get('description'),
                'prompt_text': legacy_data.get('personality_conditioning') or legacy_data.get('prompt_text'),
                'disclaimer': legacy_data.get('disclaimer'), 'tools': legacy_data.get('dependencies', [])
            }
    elif item_type == 'skill':
        return _parse_skill_metadata(item_path, repo_path=repo_path)
    else: # app, mcp, prompt
        config_path = item_path / "description.yaml"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                metadata = yaml.safe_load(f) or {}
    return metadata

DEFAULT_SEED_SKILLS = [
    {
        "folder": "python_refactoring_specialist",
        "yaml": {
            "name": "Python Refactoring Specialist",
            "author": "ParisNeo",
            "version": "1.0.0",
            "category": "Coding",
            "description": "Guides the model to refactor and optimize Python code using SOLID, DRY, KISS principles with clean type annotations."
        },
        "xml": """<skill name="python_refactoring_specialist">
  <description>Refactor and optimize Python code adhering to PEP 8, clean architecture, and type safety.</description>
  <instructions>
    1. Always audit code for algorithmic complexity and memory leaks.
    2. Enforce strict type compliance and comprehensive docstrings.
    3. Eliminate dead code, unused imports, and mutable default arguments.
    4. Provide production-ready, clean implementations without placeholders.
  </instructions>
</skill>"""
    },
    {
        "folder": "fastapi_security_auditor",
        "yaml": {
            "name": "FastAPI Security Auditor",
            "author": "ParisNeo",
            "version": "1.0.0",
            "category": "Security",
            "description": "Security directives to audit FastAPI endpoints against SSRF, IDOR, path traversal, injection, and broken authorization."
        },
        "xml": """<skill name="fastapi_security_auditor">
  <description>Zero-trust security verification for FastAPI backend services.</description>
  <instructions>
    1. Check all user-controlled path parameters and filenames with secure_filename and is_relative_to().
    2. Guard against SSRF by validating all outgoing request IPs against private/loopback/metadata blocks.
    3. Enforce object-level permissions (IDOR) on all read/write endpoints.
    4. Sanitize all markdown, HTML, and string outputs to eliminate stored XSS.
  </instructions>
</skill>"""
    },
    {
        "folder": "latex_typesetter",
        "yaml": {
            "name": "LaTeX Document Expert",
            "author": "ParisNeo",
            "version": "1.0.0",
            "category": "Documentation",
            "description": "Produces clean, compilable, publication-grade LaTeX documents, equations, and tables."
        },
        "xml": """<skill name="latex_typesetter">
  <description>Publication-grade LaTeX authoring directives.</description>
  <instructions>
    1. Structure documents with standard preamble, babel/fontenc, and geometry configurations.
    2. Write robust equation blocks using amsmath and cleveref for cross-referencing.
    3. Output self-contained LaTeX blocks that compile without missing external packages.
  </instructions>
</skill>"""
    },
    {
        "folder": "code_reviewer",
        "yaml": {
            "name": "Senior Code Reviewer",
            "author": "ParisNeo",
            "version": "1.0.0",
            "category": "Coding",
            "description": "Performs methodical, senior-level code reviews analyzing correctness, edge cases, and performance bottlenecks."
        },
        "xml": """<skill name="code_reviewer">
  <description>Senior engineering code review directives.</description>
  <instructions>
    1. Identify edge cases (empty inputs, race conditions, timeout handling).
    2. Assess performance, memory consumption, and concurrency patterns.
    3. Provide actionable suggestions with concrete code snippets.
  </instructions>
</skill>"""
    },
    {
        "folder": "markdown_technical_writer",
        "yaml": {
            "name": "Markdown Technical Writer",
            "author": "ParisNeo",
            "version": "1.0.0",
            "category": "Writing",
            "description": "Produces publication-ready technical manuals, API guides, and architectural design records."
        },
        "xml": """<skill name="markdown_technical_writer">
  <description>High-density technical writing and architectural documentation.</description>
  <instructions>
    1. Structure content logically with executive summaries, visual diagrams, and code snippets.
    2. Use GitHub Flavored Markdown tables, callouts, and clean formatting.
    3. Avoid conversational filler and focus on actionable technical substance.
  </instructions>
</skill>"""
    }
]

def ensure_skills_zoo_seeded(repo_path: Path):
    """Seeds default skills if a skill repository directory is empty."""
    try:
        repo_path.mkdir(parents=True, exist_ok=True)
        # Check if user already has skills (including SKILL.md or .xml)
        existing_skills = (
            list(repo_path.glob("**/description.yaml")) + 
            list(repo_path.glob("**/skill.xml")) +
            list(repo_path.glob("**/*skill*.md")) +
            list(repo_path.glob("**/*SKILL*.md"))
        )
        if not existing_skills and not any(repo_path.iterdir()):
            for item in DEFAULT_SEED_SKILLS:
                folder = repo_path / item["folder"]
                folder.mkdir(parents=True, exist_ok=True)
                with open(folder / "description.yaml", "w", encoding="utf-8") as f:
                    yaml.dump(item["yaml"], f)
                with open(folder / "skill.xml", "w", encoding="utf-8") as f:
                    f.write(item["xml"])
                with open(folder / "README.md", "w", encoding="utf-8") as f:
                    f.write(f"# {item['yaml']['name']}\n\n{item['yaml']['description']}\n")
    except Exception as e:
        print(f"Warning: Could not seed default skills: {e}")

def _resolve_repo_path(repo: Any, zoo_root: Path) -> Optional[Path]:
    """
    Safely resolves the filesystem path for a repository, preventing Windows WinError 123
    syntax errors when a URL is stored as repo.name.
    """
    candidates = []

    # 1. Local path if specified
    if getattr(repo, 'type', '') == 'local' and repo.url:
        try:
            lp = Path(repo.url)
            if lp.is_dir():
                return lp
        except Exception:
            pass

    # 2. Extract clean slug from name and url
    for raw in [getattr(repo, 'name', None), getattr(repo, 'url', None)]:
        if not raw:
            continue
        clean = raw.rstrip('/\\').split('/')[-1].split('\\')[-1]
        if clean.endswith('.git'):
            clean = clean[:-4]
        if ':' not in clean and clean not in candidates:
            candidates.append(clean)

    candidates.append("lollms_skills_zoo")

    for cand in candidates:
        try:
            target = zoo_root / cand
            if target.is_dir():
                return target
        except OSError:
            continue

    # 3. Fallback: check any existing directory inside zoo_root
    try:
        existing_dirs = [d for d in zoo_root.iterdir() if d.is_dir() and not d.name.startswith('.')]
        if existing_dirs:
            return existing_dirs[0]
    except Exception:
        pass

    return None

def _build_cache_for_type(db: Session, item_type: ITEM_TYPES) -> List[Dict[str, Any]]:
    items = []
    zoo_root = get_zoo_root_path(item_type)
    repo_model = get_db_repo_model(item_type)

    repositories = db.query(repo_model).all()
    repos_to_scan = []

    for repo in repositories:
        resolved = _resolve_repo_path(repo, zoo_root)
        if resolved:
            repos_to_scan.append((repo.name, resolved))

    # Also discover any unindexed directories directly inside zoo_root
    try:
        if zoo_root.is_dir():
            for d in zoo_root.iterdir():
                if d.is_dir() and not d.name.startswith('.') and not any(r[1] == d for r in repos_to_scan):
                    repos_to_scan.append((d.name, d))
    except Exception:
        pass

    for repo_name, repo_path in repos_to_scan:
        if item_type == 'skill':
            if not repo_path.is_dir() or not any(repo_path.iterdir()):
                ensure_skills_zoo_seeded(repo_path)

        if not repo_path or not repo_path.is_dir():
            continue

        # Specialized discovery for skills (handles category directories, skill subfolders with SKILL.md, and raw root files)
        if item_type == 'skill':
            seen_rel_paths = set()

            # 1. Discover folder-based skills (containing SKILL.md, skill.md, skill.xml, or description.yaml)
            folder_candidates = set()
            for root, dirs, files in os.walk(str(repo_path)):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                p_dir = Path(root)
                lower_files = {f.lower(): f for f in files}
                if any(m in lower_files for m in ['skill.md', 'skill.xml', 'description.yaml', 'description.yml']):
                    folder_candidates.add(p_dir)

            for folder in sorted(list(folder_candidates), key=lambda x: str(x)):
                rel_path = folder.relative_to(repo_path).as_posix()
                if rel_path in seen_rel_paths:
                    continue
                seen_rel_paths.add(rel_path)

                try:
                    metadata = _parse_skill_metadata(folder, repo_path=repo_path)
                    icon_path = next((p for p in [folder / "icon.png", folder / "assets" / "logo.png"] if p.exists()), None)
                    icon_b64 = None
                    if icon_path:
                        with open(icon_path, 'rb') as f:
                            icon_b64 = f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"

                    items.append(_sanitize_for_json({
                        **metadata,
                        'item_type': 'skill',
                        'repository': repo.name,
                        'folder_name': rel_path,
                        'icon': icon_b64
                    }))
                except Exception as e:
                    print(f"Warning: Could not process skill folder '{folder}' in repo '{repo.name}': {e}")

            # 2. Discover loose / raw standalone skill files (.md or .xml) not inside a registered folder
            ignore_names = {'readme.md', 'license.md', 'contributing.md', 'changelog.md', 'code_of_conduct.md', 'todo.md', 'pom.xml'}
            for root, dirs, files in os.walk(str(repo_path)):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                p_dir = Path(root)
                if any(folder == p_dir or folder in p_dir.parents for folder in folder_candidates):
                    continue

                for f in sorted(files):
                    f_lower = f.lower()
                    if f_lower in ignore_names or f.startswith('.'):
                        continue
                    if f_lower.endswith('.md') or f_lower.endswith('.xml'):
                        file_path = p_dir / f
                        rel_file = file_path.relative_to(repo_path).as_posix()
                        if rel_file in seen_rel_paths:
                            continue
                        seen_rel_paths.add(rel_file)

                        try:
                            metadata = _parse_skill_metadata(file_path, repo_path=repo_path)
                            items.append(_sanitize_for_json({
                                **metadata,
                                'item_type': 'skill',
                                'repository': repo.name,
                                'folder_name': rel_file,
                                'icon': None
                            }))
                        except Exception as e:
                            print(f"Warning: Could not process raw skill file '{file_path}' in repo '{repo.name}': {e}")
            continue

        # Standard discovery for apps, mcps, personalities, prompts
        candidate_folders = set()
        for p in repo_path.glob('**/description.yaml'):
            candidate_folders.add(p.parent)
        if item_type == 'personality':
            for p in repo_path.glob('**/config.yaml'):
                candidate_folders.add(p.parent)

        for item_folder in sorted(list(candidate_folders), key=lambda x: x.name):
            try:
                metadata = parse_item_metadata(item_folder, item_type)
                if not metadata or not metadata.get('name'):
                    metadata['name'] = item_folder.name.replace('_', ' ').title()

                if 'category' in metadata and isinstance(metadata['category'], list):
                    metadata['category'] = metadata['category'][0] if metadata['category'] else 'Generic'

                if item_type == 'personality' and (item_folder / "scripts" / "processor.py").exists():
                    metadata['is_legacy_scripted'] = True

                if item_type in ['app', 'mcp']:
                    metadata['has_dot_env_config'] = (item_folder / ".env.example").exists()

                icon_path = next((p for p in [item_folder / "icon.png", item_folder / "assets" / "logo.png"] if p.exists()), None)
                icon_b64 = None
                if icon_path:
                    with open(icon_path, 'rb') as f:
                        icon_b64 = f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"

                folder_name_rel = item_folder.relative_to(repo_path).as_posix()

                items.append(_sanitize_for_json({
                    **metadata,
                    'item_type': item_type,
                    'repository': repo.name,
                    'folder_name': folder_name_rel,
                    'icon': icon_b64
                }))
            except Exception as e:
                print(f"Warning: Could not process {item_type} item at '{item_folder}' in repo '{repo.name}': {e}")
    return items

def force_build_full_cache():
    """Builds the cache from scratch, typically for a manual refresh."""
    global _cache
    lock = FileLock(str(CACHE_LOCK_FILE), timeout=CACHE_LOCK_TIMEOUT)
    try:
        with lock:
            ASCIIColors.info("INFO: Forcing a full rebuild of the Zoo cache...")
            db = next(get_db())
            try:
                _cache["data"] = {
                    'app': _build_cache_for_type(db, 'app'),
                    'mcp': _build_cache_for_type(db, 'mcp'),
                    'prompt': _build_cache_for_type(db, 'prompt'),
                    'personality': _build_cache_for_type(db, 'personality'),
                    'skill': _build_cache_for_type(db, 'skill'),
                }
                _cache["timestamp"] = time.time()
                with open(CACHE_FILE, 'w') as f:
                    json.dump(_cache, f)
                ASCIIColors.green("INFO: Zoo cache rebuild complete.")
            finally:
                db.close()
    except Timeout:
        ASCIIColors.warning("Could not acquire lock for force cache build. Another process might be building it.")

def refresh_repo_cache(repo_name: str, item_type: ITEM_TYPES):
    global _cache
    lock = FileLock(str(CACHE_LOCK_FILE), timeout=60)
    try:
        with lock:
            if not _cache.get("data"):
                load_cache()
            
            _cache["data"][item_type] = [item for item in _cache.get("data", {}).get(item_type, []) if item.get('repository') != repo_name]
            
            db = next(get_db())
            try:
                repo = db.query(get_db_repo_model(item_type)).filter_by(name=repo_name).first()
                if repo:
                    repo_path = Path(repo.url) if repo.type == 'local' else get_zoo_root_path(item_type) / repo.name
                    if repo_path.is_dir():
                        config_files = list(repo_path.glob('**/description.yaml'))
                        if item_type == 'personality': config_files.extend(list(repo_path.glob('**/config.yaml')))
                        elif item_type == 'skill': config_files.extend(list(repo_path.glob('**/skill.xml')))

                        for config_file in config_files:
                            item_folder = config_file.parent
                            try:
                                metadata = parse_item_metadata(item_folder, item_type)
                                if not metadata.get('name'): metadata['name'] = item_folder.name
                                if 'category' in metadata and isinstance(metadata['category'], list):
                                    metadata['category'] = metadata['category'][0] if metadata['category'] else 'Uncategorized'
                                if item_type == 'personality' and (item_folder / "scripts" / "processor.py").exists():
                                    metadata['is_legacy_scripted'] = True
                                if item_type in ['app', 'mcp']:
                                    metadata['has_dot_env_config'] = (item_folder / ".env.example").exists()
                                icon_path = next((p for p in [item_folder / "icon.png", item_folder / "assets" / "logo.png"] if p.exists()), None)
                                icon_b64 = f"data:image/png;base64,{base64.b64encode(icon_path.read_bytes()).decode('utf-8')}" if icon_path else None
                                folder_name_rel = item_folder.relative_to(repo_path).as_posix()
                                _cache["data"][item_type].append(_sanitize_for_json({**metadata, 'item_type': item_type, 'repository': repo.name, 'folder_name': folder_name_rel, 'icon': icon_b64}))
                            except Exception as e:
                                print(f"Warning: Could not process item '{item_folder}' on refresh: {e}")

                _cache["timestamp"] = time.time()
                with open(CACHE_FILE, 'w') as f: json.dump(_cache, f)
            finally:
                db.close()
    except Timeout:
        ASCIIColors.warning(f"Could not acquire lock to refresh repo '{repo_name}'. Cache may be slightly stale.")


def load_cache():
    """Loads the cache from file if it exists, otherwise builds it."""
    global _cache
    required_keys = {'app', 'mcp', 'prompt', 'personality', 'skill'}

    if _cache.get("data") and required_keys.issubset(_cache.get("data", {}).keys()):
        return

    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r') as f:
                disk_cache = json.load(f)
                if disk_cache.get("data") and required_keys.issubset(disk_cache.get("data", {}).keys()):
                    _cache = disk_cache
                    return
        except (json.JSONDecodeError, TypeError):
            ASCIIColors.warning("Cache file is corrupted, rebuilding.")

    # Rebuild if not in memory, file doesn't exist, or missing required keys like 'skill'
    force_build_full_cache()

def refresh_item_type_cache(item_type: ITEM_TYPES):
    """Targeted refresh of a single modality without locking the entire universe."""
    global _cache
    db = next(get_db())
    try:
        if not _cache.get("data"):
            _cache["data"] = {}
        _cache["data"][item_type] = _build_cache_for_type(db, item_type)
        _cache["timestamp"] = time.time()
        try:
            with open(CACHE_FILE, 'w') as f:
                json.dump(_cache, f)
        except Exception:
            pass
    finally:
        db.close()

def get_all_items(item_type: ITEM_TYPES) -> List[Dict[str, Any]]:
    load_cache()
    items = _cache.get("data", {}).get(item_type)
    if items is None or (item_type == 'skill' and len(items) == 0):
        refresh_item_type_cache(item_type)
        items = _cache.get("data", {}).get(item_type, [])
    return items or []

def get_all_categories(item_type: ITEM_TYPES) -> List[str]:
    items = get_all_items(item_type)
    categories = {'All'}
    for item in items:
        if item.get('category'):
            categories.add(item['category'])
    return sorted(list(categories))