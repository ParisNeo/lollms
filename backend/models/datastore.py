# backend/models/datastore.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime

class DataStoreBase(BaseModel):
    name: str
    description: Optional[str] = None

class DataStoreCreate(DataStoreBase):
    vectorizer_name: str
    vectorizer_config: Dict[str, Any] = Field(default_factory=dict)
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    chunking_strategy: Optional[str] = "recursive"
    chunking_kwargs: Optional[Dict[str, Any]] = Field(default_factory=dict)

class DataStoreEdit(DataStoreBase):
    chunking_strategy: Optional[str] = None
    chunking_kwargs: Optional[Dict[str, Any]] = None

class DataStorePublic(DataStoreBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    owner_username: str
    permission_level: str
    vectorizer_name: str
    vectorizer_config: Dict[str, Any]
    chunk_size: int
    chunk_overlap: int
    chunking_strategy: str = "recursive"
    chunking_kwargs: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: Optional[datetime] = None

class DataStoreShareRequest(BaseModel):
    target_username: str
    permission_level: str

class SharedWithUserPublic(BaseModel):
    user_id: int
    username: str
    icon: Optional[str]
    permission_level: str

class DataStoreRevectorizeRequest(BaseModel):
    vectorizer_name: str
    vectorizer_config: Dict[str, Any] = Field(default_factory=dict)

class SafeStoreDocumentInfo(BaseModel):
    filename: str
    metadata: Optional[Dict[str, Any]] = None
    chunk_count: Optional[int] = None
    char_count: Optional[int] = None

class ScrapeRequest(BaseModel):
    url: str
    depth: int = 0

class DataStoreQueryRequest(BaseModel):
    query: str
    top_k: int = 10
    min_similarity_percent: float = 50.0
    mode: str = "hybrid"  # "dense" | "hybrid"
    retrieval_target: str = "chunks"  # "chunks" | "window" | "full_documents"
    window_before: int = 1
    window_after: int = 1
    dense_weight: float = 0.5
    bm25_weight: float = 0.5
    rrf_k: int = 60

class DataStoreAnswerRequest(DataStoreQueryRequest):
    system_prompt: Optional[str] = None
    max_tokens: Optional[int] = 2048
    temperature: Optional[float] = 0.2

class FullDocumentQueryRequest(BaseModel):
    query: str
    top_k_docs: int = 2
    search_mode: str = "hybrid"

class DocumentWindowQueryRequest(BaseModel):
    query: str
    top_k_hits: int = 3
    window_before: int = 1
    window_after: int = 1

class DocumentChunksPaginatedResponse(BaseModel):
    document_id: str
    page: int
    page_size: int
    total_pages: int
    total_chunks: int
    chunks: List[Dict[str, Any]]

class DataStoreAnswerResponse(BaseModel):
    answer: str
    chunks: List[Dict[str, Any]]
    model_name: Optional[str] = None

class SparqlQueryRequest(BaseModel):
    query: str

class GraphHybridQueryRequest(BaseModel):
    query: str
    top_k: int = 5
    dense_weight: float = 0.4
    bm25_weight: float = 0.3
    graph_weight: float = 0.3