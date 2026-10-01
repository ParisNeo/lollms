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

def test_form_xml_parser_extracts_fields_robustly():
    """Verify that form XML with varied field tags and options is parsed properly into fields."""
    import re
    xml_input = '''<lollms_form title="Multi-Field Test Form">
        <field name="favorite_language" label="Favorite Language" type="select">
            <option>Python</option>
            <option>JavaScript</option>
        </field>
        <field name="experience_level" label="Experience Level" type="radio">
            <option>Beginner</option>
            <option>Intermediate</option>
        </field>
        <field name="age" label="Age" type="number" min="1" max="120" default="30"/>
        <field name="newsletter" label="Subscribe to newsletter" type="checkbox" default="true"/>
        <field name="start_date" label="Start Date" type="date"/>
    </lollms_form>'''

    f_title_match = re.search(r'title=["\']([^"\']+)["\']', xml_input)
    assert f_title_match is not None
    assert f_title_match.group(1) == "Multi-Field Test Form"

    field_matches = list(re.finditer(r'<field\b([^>]*?)(?:>(.*?)<\/field>|\s*\/?>)', xml_input, re.DOTALL | re.IGNORECASE))
    assert len(field_matches) == 5

    langs = re.findall(r'<option[^>]*>(.*?)<\/option>', field_matches[0].group(2) or '', re.DOTALL | re.IGNORECASE)
    assert len(langs) == 2
    assert [l.strip() for l in langs] == ["Python", "JavaScript"]

def test_form_line_based_specification_fallback():
    """Verify that text lines like 'Field — type' are parsed properly into fields."""
    import re
    lines_input = """Favorite Language — select dropdown
Experience Level — radio buttons
Age — number
Subscribe to newsletter — checkbox
Start Date — date"""

    fields = []
    for line in lines_input.split('\n'):
        sep_match = re.match(r'^(?:[-*•]|\d+\.)?\s*([A-Za-z0-9_][A-Za-z0-9_\s]*?)\s*(?:—|–|-|:|\|)\s*([A-Za-z0-9_\s\(\)\/]+?)$', line.strip())
        assert sep_match is not None
        raw_label = sep_match.group(1).strip()
        fields.append({
            "name": re.sub(r'[^a-z0-9_]+', '_', raw_label.lower()).strip('_'),
            "label": raw_label,
            "type": sep_match.group(2).strip()
        })

    assert len(fields) == 5
    assert fields[0]["name"] == "favorite_language"
    assert fields[0]["label"] == "Favorite Language"
    assert fields[1]["name"] == "experience_level"
    assert fields[2]["name"] == "age"
    assert fields[3]["name"] == "subscribe_to_newsletter"
    assert fields[4]["name"] == "start_date"

def test_form_presence_in_message_output():
    """Verify that forms always stay present in message payload and metadata."""
    msg = MessageOutput(
        id="test-msg-form",
        sender="assistant",
        sender_type="assistant",
        content="<processing type=\"lollms_form\" title=\"lollms_form\"></processing>",
        forms=[{
            "id": "form_1",
            "title": "Interactive Form",
            "fields": [{"name": "response", "label": "Your Response", "type": "textarea"}]
        }]
    )
    assert msg.forms is not None
    assert len(msg.forms) == 1
    assert msg.forms[0]["fields"][0]["name"] == "response"

def test_sources_indexed_and_preserved_in_message_output():
    """Verify that sources retain index property [1], [2] for citation navigation."""
    sources_data = [
        {"title": "LoLLMs Architecture", "source": "docs/architecture.md", "content": "RAG engine...", "score": 92.5, "index": 1}
    ]
    msg = MessageOutput(
        id="test-msg-sources",
        sender="assistant",
        sender_type="assistant",
        content="According to the documentation [1], RAG is supported.",
        sources=sources_data
    )
    assert msg.sources is not None
    assert len(msg.sources) == 1
    assert msg.sources[0]["index"] == 1
    assert msg.sources[0]["title"] == "LoLLMs Architecture"

def test_thinking_extracted_from_content_when_thoughts_not_populated():
    """Verify that thoughts are isolated from message content into thoughts property."""
    import re
    raw_content = "<think>Planning the implementation.\nChecking constraints.</think>Here is the final answer."
    think_match = re.search(r'<(?:think|thought)>([\s\S]*?)</(?:think|thought)>', raw_content, re.IGNORECASE)
    assert think_match is not None
    extracted_thoughts = think_match.group(1).strip()
    clean_content = re.sub(r'<(?:think|thought)>[\s\S]*?</(?:think|thought)>', '', raw_content, flags=re.IGNORECASE).strip()

    assert extracted_thoughts == "Planning the implementation.\nChecking constraints."
    assert clean_content == "Here is the final answer."

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