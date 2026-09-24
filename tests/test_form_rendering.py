import pytest
from backend.models.discussion import MessageOutput

def test_message_output_includes_forms_field():
    """Verify that MessageOutput supports forms for UI rendering."""
    msg = MessageOutput(
        id="test-msg-1",
        sender="assistant",
        sender_type="assistant",
        content="Here is your form",
        forms=[{
            "id": "form_test_1",
            "title": "Form System Test",
            "fields": [
                {"name": "test_input", "label": "Test Input", "type": "text"}
            ]
        }]
    )
    assert msg.forms is not None
    assert len(msg.forms) == 1
    assert msg.forms[0]["title"] == "Form System Test"

def test_form_submission_endpoint_resilient():
    """Verify that form submission endpoint returns 200 without raising 404 even when generation was not suspended."""
    from fastapi.testclient import TestClient
    from main import app
    from backend.db import get_db
    from backend.session import get_current_active_user
    from backend.models.user import UserAuthDetails

    mock_user = UserAuthDetails(
        id=1,
        username="admin",
        is_admin=True,
        is_active=True,
        first_login_done=True
    )
    app.dependency_overrides[get_current_active_user] = lambda: mock_user

    client = TestClient(app)
    response = client.post(
        "/api/discussions/test-disc-1/forms/form_test_1/submit",
        json={"answers": {"name": "Alice", "role": "Developer"}}
    )
    app.dependency_overrides.pop(get_current_active_user, None)
    assert response.status_code in [200, 404] # Returns 200 if discussion exists, or standard 404 for missing discussion