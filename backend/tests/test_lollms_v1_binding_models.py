from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from backend.db.base import Base
from backend.db import get_db
from backend.db.models.user import User as DBUser
from backend.db.models.config import (
    LLMBinding as DBLLMBinding,
    TTIBinding as DBTTIBinding
)
from backend.routers.services.lollms_v1 import get_user_for_lollms_service

# In-memory test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

mock_admin = DBUser(
    id=1,
    username="testadmin",
    is_admin=True,
    is_active=True,
    status="active"
)

def override_get_user():
    return mock_admin

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_for_lollms_service] = override_get_user

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Seed an LLM binding and a TTI binding
    llm_binding = DBLLMBinding(
        alias="test_ollama",
        name="ollama",
        config={},
        default_model_name="llama3.1:latest",
        is_active=True,
        model_aliases={"llama3.1:latest": {"title": "Llama 3.1 8B Instruct", "has_vision": False}}
    )
    tti_binding = DBTTIBinding(
        alias="test_diffusers",
        name="diffusers",
        config={},
        default_model_name="sdxl_turbo",
        is_active=True,
        model_aliases={"sdxl_turbo": {"title": "SDXL Turbo Fast"}}
    )
    db.add_all([llm_binding, tti_binding])
    db.commit()
    db.close()

    # Prevent heavy external binding server processes from spinning up during tests
    with patch("backend.routers.services.lollms_v1._extract_raw_models_for_binding", return_value=[]):
        yield

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_user_for_lollms_service, None)

def test_list_llm_models():
    client = TestClient(app)
    response = client.get("/lollms/v1/llm/models")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert data["binding_type"] == "llm"
    assert data["total"] >= 1
    model_ids = [m["id"] for m in data["data"]]
    assert "test_ollama/llama3.1:latest" in model_ids
    matched = next(m for m in data["data"] if m["id"] == "test_ollama/llama3.1:latest")
    assert matched["name"] == "Llama 3.1 8B Instruct"
    assert matched["binding"] == "test_ollama"
    assert matched["model_name"] == "llama3.1:latest"

def test_list_tti_models():
    client = TestClient(app)
    response = client.get("/lollms/v1/tti/models")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert data["binding_type"] == "tti"
    assert data["total"] >= 1
    model_ids = [m["id"] for m in data["data"]]
    assert "test_diffusers/sdxl_turbo" in model_ids

def test_list_models_with_alias_normalization():
    client = TestClient(app)
    response = client.get("/lollms/v1/image/models")
    assert response.status_code == 200
    data = response.json()
    assert data["binding_type"] == "tti"

def test_list_models_invalid_type():
    client = TestClient(app)
    response = client.get("/lollms/v1/unknown_modality/models")
    assert response.status_code == 400
    assert "Unsupported binding type" in response.json()["detail"]

def test_list_models_convenience_endpoint():
    client = TestClient(app)
    response = client.get("/lollms/v1/models?binding_type=tti")
    assert response.status_code == 200
    data = response.json()
    assert data["binding_type"] == "tti"