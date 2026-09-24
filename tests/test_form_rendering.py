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