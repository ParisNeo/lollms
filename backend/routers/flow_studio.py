import uuid
import json
import traceback
import base64
import re
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.db.models.flow import Flow as DBFlow, FlowNodeDefinition as DBFlowNodeDefinition
from backend.db.models.user import User as DBUser
from backend.models.flow import FlowCreate, FlowUpdate, FlowPublic, FlowExecuteRequest, FlowNodeDefCreate, FlowNodeDefPublic
from backend.security import send_generic_email, _convert_html_to_text
from backend.session import get_current_active_user, get_current_admin_user, build_lollms_client_from_params
from backend.models import UserAuthDetails, TaskInfo
from backend.task_manager import task_manager, Task
from backend.flow_engine import FlowEngine
from backend.settings import settings

router = APIRouter(prefix="/api/flows", tags=["Flow Studio"])

# --- Models for Code Gen/Test ---
class GenerateCodeRequest(BaseModel):
    prompt: str
    current_inputs: Optional[List[Dict[str, Any]]] = None 
    current_outputs: Optional[List[Dict[str, Any]]] = None

class TestCodeRequest(BaseModel):
    code: str
    inputs: Dict[str, Any]
    requirements: List[str] = []

# --- Flow Definitions (Nodes) ---

@router.get("/nodes", response_model=List[FlowNodeDefPublic])
def list_node_definitions(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return db.query(DBFlowNodeDefinition).all()

@router.post("/nodes", response_model=FlowNodeDefPublic)
def create_node_definition(
    def_data: FlowNodeDefCreate,
    current_user: UserAuthDetails = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    if db.query(DBFlowNodeDefinition).filter(DBFlowNodeDefinition.name == def_data.name).first():
        raise HTTPException(status_code=400, detail="Node type name already exists")

    # Dual-Layer Security Audit (AST + Cognitive AI Review)
    from backend.security import verify_custom_node_code
    lc = build_lollms_client_from_params(current_user.username)
    is_safe, error_msg = verify_custom_node_code(def_data.code, lc)
    if not is_safe:
        raise HTTPException(status_code=400, detail=f"Security Rejection: {error_msg}")

    new_def = DBFlowNodeDefinition(**def_data.model_dump())
    db.add(new_def)
    db.commit()
    db.refresh(new_def)
    return new_def

@router.put("/nodes/{node_id}", response_model=FlowNodeDefPublic)
def update_node_definition(
    node_id: str,
    def_data: FlowNodeDefCreate,
    current_user: UserAuthDetails = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    node = db.query(DBFlowNodeDefinition).filter(DBFlowNodeDefinition.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node definition not found")

    # Dual-Layer Security Audit (AST + Cognitive AI Review)
    from backend.security import verify_custom_node_code
    lc = build_lollms_client_from_params(current_user.username)
    is_safe, error_msg = verify_custom_node_code(def_data.code, lc)
    if not is_safe:
        raise HTTPException(status_code=400, detail=f"Security Rejection: {error_msg}")

    for field, value in def_data.model_dump().items():
        setattr(node, field, value)

    db.commit()
    db.refresh(node)
    return node

@router.delete("/nodes/{node_id}")
def delete_node_definition(
    node_id: str,
    current_user: UserAuthDetails = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    node = db.query(DBFlowNodeDefinition).filter(DBFlowNodeDefinition.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node definition not found")
    db.delete(node)
    db.commit()
    return {"message": "Node definition deleted"}

@router.post("/nodes/{node_id}/flag")
def flag_node_as_unsafe(
    node_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    node = db.query(DBFlowNodeDefinition).filter(DBFlowNodeDefinition.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node definition not found")

    # Retrieve all system administrators
    admins = db.query(DBUser).filter(DBUser.is_admin == True).all()
    if not admins:
        raise HTTPException(status_code=500, detail="No system administrators configured to receive the security alert.")

    # Construct the security alert email
    subject = f"⚠️ SECURITY ALERT: Custom Node '{node.label}' Flagged as UNSAFE"
    body = f"""
    <p>Hello Administrator,</p>
    <p>An active user (<b>{current_user.username}</b>) has flagged the following custom node definition in the system as <b>UNSAFE / MALICIOUS</b>:</p>
    <ul>
        <li><b>Node ID:</b> {node.id}</li>
        <li><b>Node Name/Type:</b> {node.name}</li>
        <li><b>Node Label:</b> {node.label}</li>
        <li><b>Category:</b> {node.category}</li>
        <li><b>Description:</b> {node.description}</li>
    </ul>
    <p><b>CRITICAL SECURITY WARNING:</b> Since only administrators are authorized to publish custom node definitions, a user-flagged malicious node indicates a high probability of **compromise on one of your administrative accounts** or un-vetted third-party import.</p>
    <p>Please review the node's source code immediately in the Flow Studio admin panel or directly in the database. If necessary, delete the node or deactivate compromised accounts.</p>
    <p>This is an automated security broadcast from your LoLLMs instance.</p>
    """

    email_sent_count = 0
    text_content = _convert_html_to_text(body)
    for admin in admins:
        if admin.email:
            try:
                send_generic_email(
                    admin.email, 
                    subject, 
                    body, 
                    background_color="#fff1f0", # Light red alert tint
                    send_as_text=False
                )
                email_sent_count += 1
            except Exception as e:
                print(f"Failed to send security alert to admin {admin.username}: {e}")

    return {"message": "Node successfully flagged. Security alerts have been dispatched to system administrators.", "admins_notified": email_sent_count}

# --- Code Generation & Debugging ---

def extract_json_from_text(text: str):
    """Attempts to find and parse JSON object from text."""
    try: return json.loads(text)
    except json.JSONDecodeError: pass
    match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        try: return json.loads(match.group(1))
        except: pass
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        try: return json.loads(text[start:end+1])
        except: pass
    return None

@router.post("/generate_code")
def generate_node_design(
    req: GenerateCodeRequest,
    current_user: UserAuthDetails = Depends(get_current_admin_user)
):
    client = build_lollms_client_from_params(current_user.username)
    supported_types = "string, int, float, boolean, image, node_ref, model_selection, list, any"
    
    system_prompt = f"""You are an expert Python developer for the Lollms Flow Studio.
Design a custom node based on the user's description.
Output a single valid JSON object.

### JSON Structure
{{
  "name": "snake_case_id",
  "label": "Human Label",
  "category": "General | AI Generation | Video | Audio | Transformers | Logic",
  "description": "Short description",
  "color": "Tailwind bg and border classes",
  "inputs": [ {{ "name": "var", "type": "valid_type" }} ],
  "outputs": [ {{ "name": "var", "type": "valid_type" }} ],
  "requirements": ["list", "of", "pip", "packages"],
  "code": "Python code string"
}}

### Code Requirements
- Class: `CustomNode`
- Method: `def execute(self, inputs, context):`
- `context.lollms_client`: Access to AI.
- `context.get_client(model_name=None)`: Get client for specific model.

IMPORTANT: Respond ONLY with JSON.
"""
    user_prompt = f"Design a node that: {req.prompt}"
    generated_text = client.generate_text(user_prompt, system_prompt=system_prompt, max_new_tokens=2048)
    data = extract_json_from_text(generated_text)
    if not data:
        raise HTTPException(status_code=500, detail="AI failed to generate valid JSON.")
    return data


@router.post("/test_code")
def test_node_code(
    req: TestCodeRequest,
    current_user: UserAuthDetails = Depends(get_current_admin_user)
):
    # Dual-Layer Security Audit (AST + Cognitive AI Review)
    from backend.security import verify_custom_node_code
    lc = build_lollms_client_from_params(current_user.username)
    is_safe, error_msg = verify_custom_node_code(req.code, lc)
    if not is_safe:
        return {"status": "error", "error": f"Security Rejection: {error_msg}"}

    try:
        # Handle Requirements
        import pipmaster
        for r in req.requirements:
            if not pipmaster.is_installed(r):
                pipmaster.install(r)

        local_scope = {}
        try:
            exec(req.code, {}, local_scope)
        except Exception as e:
            return {"status": "error", "error": f"Compilation Error: {str(e)}", "traceback": traceback.format_exc()}
        
        NodeClass = local_scope.get("CustomNode")
        if not NodeClass:
            return {"status": "error", "error": "Class 'CustomNode' not found."}
            
        class MockContext:
            def __init__(self, user):
                self.username = user
                self.lollms_client = build_lollms_client_from_params(user)
            def get_client(self, model_name=None): return self.lollms_client

        node_instance = NodeClass()
        try:
            result = node_instance.execute(req.inputs, MockContext(current_user.username))
            return {"status": "success", "output": result} 
        except Exception as e:
            return {"status": "error", "error": f"Runtime Error: {str(e)}", "traceback": traceback.format_exc()}
    except Exception as e:
        return {"status": "error", "error": f"System Error: {str(e)}"}

# --- Workflows ---

@router.get("", response_model=List[FlowPublic])
def list_flows(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return db.query(DBFlow).filter(DBFlow.owner_user_id == current_user.id).order_by(DBFlow.updated_at.desc()).all()

@router.post("", response_model=FlowPublic)
def create_flow(
    flow_data: FlowCreate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    new_flow = DBFlow(
        name=flow_data.name,
        description=flow_data.description,
        data=flow_data.data,
        owner_user_id=current_user.id
    )
    db.add(new_flow)
    db.commit()
    db.refresh(new_flow)
    return new_flow

@router.get("/{flow_id}", response_model=FlowPublic)
def get_flow(
    flow_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    flow = db.query(DBFlow).filter(DBFlow.id == flow_id, DBFlow.owner_user_id == current_user.id).first()
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    return flow

@router.put("/{flow_id}", response_model=FlowPublic)
def update_flow(
    flow_id: str,
    flow_data: FlowUpdate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    flow = db.query(DBFlow).filter(DBFlow.id == flow_id, DBFlow.owner_user_id == current_user.id).first()
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    
    flow.name = flow_data.name
    flow.description = flow_data.description
    flow.data = flow_data.data
    db.commit()
    db.refresh(flow)
    return flow

@router.delete("/{flow_id}")
def delete_flow(
    flow_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    flow = db.query(DBFlow).filter(DBFlow.id == flow_id, DBFlow.owner_user_id == current_user.id).first()
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    db.delete(flow)
    db.commit()
    return {"message": "Flow deleted"}

def _execute_flow_task(task: Task, username: str, flow_id: str, graph_data: dict, inputs: dict = None):
    engine = FlowEngine(username)
    if inputs:
        node_map = {n['id']: n for n in graph_data.get('nodes', [])}
        for node_id, node_inputs in inputs.items():
            if node_id in node_map:
                if 'data' not in node_map[node_id]: node_map[node_id]['data'] = {}
                node_map[node_id]['data'].update(node_inputs)
    
    task.log("Starting flow execution...")
    task.set_progress(10)
    try:
        results = engine.execute_graph(graph_data)
        task.set_progress(100)
        return results
    except Exception as e:
        task.log(f"Execution failed: {str(e)}", level="ERROR")
        raise e

@router.post("/execute", response_model=TaskInfo)
def execute_flow(
    request: FlowExecuteRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    flow = db.query(DBFlow).filter(DBFlow.id == request.flow_id, DBFlow.owner_user_id == current_user.id).first()
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    
    task = task_manager.submit_task(
        name=f"Execute Flow: {flow.name}",
        target=_execute_flow_task,
        args=(current_user.username, flow.id, flow.data, request.inputs),
        description=f"Running workflow {flow.id}",
        owner_username=current_user.username
    )
    return task
