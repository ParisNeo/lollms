# backend/models/fun_fact.py
from pydantic import BaseModel, Field, constr
from typing import Optional, List

# --- Welcome View Models ---
class WelcomeInfo(BaseModel):
    welcome_text: Optional[str] = None
    welcome_slogan: Optional[str] = None
    welcome_logo_url: Optional[str] = None
    fun_fact: str
    fun_fact_color: Optional[str] = None
    fun_fact_category: Optional[str] = None


# --- Fun Fact Management Models (For Admin) ---
class FunFactCategoryBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    is_active: bool = True
    color: str = Field(default="#3B82F6", pattern=r"^#[0-9a-fA-F]{6}$")

class FunFactCategoryCreate(FunFactCategoryBase):
    pass

class FunFactCategoryUpdate(BaseModel):
    name: Optional[constr(min_length=1, max_length=100)] = None
    is_active: Optional[bool] = None
    color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")

class FunFactCategoryPublic(FunFactCategoryBase):
    id: int
    class Config:
        from_attributes = True

class FunFactBase(BaseModel):
    content: constr(min_length=1)
    category_id: int

class FunFactCreate(FunFactBase):
    pass

class FunFactUpdate(BaseModel):
    content: Optional[constr(min_length=1)] = None
    category_id: Optional[int] = None

class FunFactPublic(FunFactBase):
    id: int
    category: FunFactCategoryPublic
    class Config:
        from_attributes = True

# For Bulk Import/Export
class FunFactExport(BaseModel):
    category: str
    content: str

class FunFactsImportRequest(BaseModel):
    fun_facts: List[FunFactExport]

# NEW: For single category Import/Export
class FunFactCategoryExport(FunFactCategoryBase):
    facts: List[str]

class FunFactCategoryImport(FunFactCategoryBase):
    facts: List[str]