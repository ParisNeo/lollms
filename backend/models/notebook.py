from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class StructureItem(BaseModel):
    title: str
    type: str = "markdown" 
    content: Optional[str] = ""

class ArxivConfig(BaseModel):
    max_results: int = 3
    sort_by: str = "Relevance" # Relevance, SubmittedDate, LastUpdatedDate

class ArxivSearchRequest(BaseModel):
    query: str
    max_results: int = 5

class ArxivResult(BaseModel):
    entry_id: str
    title: str
    authors: List[str]
    summary: str
    published: str
    pdf_url: str

class ArxivSelected(BaseModel):
    entry_id: str
    title: str
    authors: List[str]
    summary: str
    pdf_url: str
    ingest_full: bool = False

class NotebookCreate(BaseModel):
    title: str
    content: Optional[str] = ""
    type: Optional[str] = "generic"
    language: Optional[str] = "en"
    structure: Optional[List[StructureItem]] = None 
    initialPrompt: Optional[str] = None
    urls: Optional[List[str]] = None
    youtube_urls: Optional[List[str]] = None
    wikipedia_urls: Optional[List[str]] = None
    google_search_queries: Optional[List[str]] = None
    arxiv_queries: Optional[List[str]] = None
    arxiv_selected: Optional[List[ArxivSelected]] = None
    arxiv_config: Optional[ArxivConfig] = None
    youtube_configs: Optional[List[Dict[str, str]]] = None
    raw_text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    delay_processing: bool = False # Flag to skip auto-ingestion

class NotebookUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    language: Optional[str] = None
    artefacts: Optional[List[Dict[str, Any]]] = None
    tabs: Optional[List[Dict[str, Any]]] = None

class NotebookResponse(BaseModel):
    id: str
    title: str
    content: str
    type: str
    language: str
    artefacts: List[Dict[str, Any]]
    tabs: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class GenerateStructureRequest(BaseModel):
    type: str
    prompt: str
    urls: Optional[List[str]] = []
    files: Optional[List[Any]] = [] 

class GenerateTitleResponse(BaseModel):
    title: str

class ProcessRequest(BaseModel):
    prompt: str
    input_tab_ids: List[str]
    output_type: str
    target_tab_id: Optional[str] = None
    selected_artefacts: Optional[List[str]] = []
    skip_llm: bool = False
    generate_speech: bool = False
