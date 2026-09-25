import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

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
    TTIBinding as DBTTIBinding,
    TTSBinding as DBTTSBinding,
    STTBinding as DBSTTBinding
)
from backend.routers.services.openai_v1 import get_user_from_api_key

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

mock_user = DBUser(
    id=1,
    username="testuser",
    is_admin=True,
    is_active=True,
    status="active"
)

def override_get_user():
    return mock_user

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_from_api_key] = override_get_user

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    llm = DBLLMBinding(
        alias="test_llm",
        name="mock_llm",
        config={},
        default_model_name="mock_model",
        is_active=True,
        model_aliases={"mock_model": {"title": "Mock Model 8B"}}
    )
    tts = DBTTSBinding(
        alias="test_tts",
        name="mock_tts",
        config={},
        default_model_name="mock_voice_model",
        is_active=True
    )
    stt = DBSTTBinding(
        alias="test_stt",
        name="mock_stt",
        config={},
        default_model_name="mock_whisper",
        is_active=True
    )
    db.add_all([llm, tts, stt])
    db.commit()
    db.close()

    yield

    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_user_from_api_key, None)

def test_list_models_returns_universal_profiles():
    client = TestClient(app)

    # 1. Default mode: profiles_only returns clean profile name as ID
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert isinstance(data["data"], list)
    assert len(data["data"]) > 0

    model_ids = [m["id"] for m in data["data"]]
    assert "Mock Model 8B" in model_ids or "test_llm/mock_model" in model_ids

    for item in data["data"]:
        assert item["object"] == "model"
        assert "created" in item
        assert "owned_by" in item

    # 2. Mode all_models: returns models in binding/model format
    resp_all = client.get("/v1/models?mode=all_models")
    assert resp_all.status_code == 200
    all_data = resp_all.json()
    all_ids = [m["id"] for m in all_data["data"]]
    assert "test_llm/mock_model" in all_ids

def test_auto_create_profiles_endpoint():
    client = TestClient(app)
    # Target test_llm binding (id=1)
    response = client.post("/api/admin/bindings/1/auto-create-profiles?modality=llm")
    assert response.status_code == 200
    res_data = response.json()
    assert "total_profiles" in res_data

def test_user_personal_stats_endpoint():
    client = TestClient(app)
    response = client.get("/api/users/me/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_tokens" in data
    assert "total_energy_kwh" in data
    assert "total_co2_g" in data
    assert "co2_equivalents" in data
    assert "source_breakdown" in data
    assert "webui_tokens" in data["source_breakdown"]
    assert "api_tokens" in data["source_breakdown"]
    assert "webui_ratio" in data["source_breakdown"]
    assert "api_ratio" in data["source_breakdown"]
    assert "webui_tokens_per_day" in data
    assert "api_tokens_per_day" in data

def test_chat_completions_structured_output_json_schema():
    client = TestClient(app)

    mock_lc = MagicMock()
    mock_lc.generate_from_messages.return_value = '{"answer": "Paris", "confidence": 0.99}'
    mock_lc.count_tokens.return_value = 10

    with patch("backend.routers.services.openai_v1.build_lollms_client_from_params", return_value=mock_lc):
        response = client.post("/v1/chat/completions", json={
            "model": "test_llm/mock_model",
            "messages": [{"role": "user", "content": "What is the capital of France?"}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "CapitalAnswer",
                    "schema": {
                        "type": "object",
                        "properties": {"answer": {"type": "string"}, "confidence": {"type": "number"}},
                        "required": ["answer", "confidence"]
                    },
                    "strict": True
                }
            }
        })

    assert response.status_code == 200
    data = response.json()
    assert data["choices"][0]["message"]["content"] == '{"answer": "Paris", "confidence": 0.99}'

def test_chat_completions_reasoning_content_extraction():
    client = TestClient(app)

    mock_lc = MagicMock()
    mock_lc.generate_from_messages.return_value = '<think>I need to add 2 and 2 to get 4.</think>The result is 4.'
    mock_lc.count_tokens.return_value = 15

    with patch("backend.routers.services.openai_v1.build_lollms_client_from_params", return_value=mock_lc):
        response = client.post("/v1/chat/completions", json={
            "model": "test_llm/mock_model",
            "messages": [{"role": "user", "content": "Calculate 2 + 2"}],
            "max_completion_tokens": 512,
            "reasoning_effort": "medium"
        })

    assert response.status_code == 200
    data = response.json()
    message = data["choices"][0]["message"]
    assert message["content"] == "The result is 4."
    assert message["reasoning_content"] == "I need to add 2 and 2 to get 4."
    assert "completion_tokens_details" in data["usage"]

def test_audio_speech_endpoint():
    client = TestClient(app)

    mock_lc = MagicMock()
    mock_lc.tts.generate_audio.return_value = b"FAKE_AUDIO_BYTES_MP3"

    with patch("backend.routers.services.openai_v1.build_lollms_client_from_params", return_value=mock_lc):
        response = client.post("/v1/audio/speech", json={
            "model": "test_tts/mock_voice_model",
            "input": "Testing audio speech output.",
            "voice": "alloy",
            "response_format": "mp3"
        })

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"FAKE_AUDIO_BYTES_MP3"

def test_responses_api_endpoint():
    client = TestClient(app)

    mock_lc = MagicMock()
    mock_lc.generate_from_messages.return_value = "This is a response from the new Responses API primitive."
    mock_lc.count_tokens.return_value = 20

    with patch("backend.routers.services.openai_v1.build_lollms_client_from_params", return_value=mock_lc):
        response = client.post("/v1/responses", json={
            "model": "test_llm/mock_model",
            "instructions": "Be concise.",
            "input": "Summarize AI agents in 2026."
        })

    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "response"
    assert data["status"] == "completed"
    assert len(data["output"]) == 1
    assert data["output"][0]["content"][0]["text"] == "This is a response from the new Responses API primitive."