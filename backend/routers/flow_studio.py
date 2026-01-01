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
from backend.models.flow import FlowCreate, FlowUpdate, FlowPublic, FlowExecuteRequest, FlowNodeDefCreate, FlowNodeDefPublic
from backend.session import get_current_active_user, get_current_admin_user, build_lollms_client_from_params
from backend.models import UserAuthDetails, TaskInfo
from backend.task_manager import task_manager, Task
from backend.flow_engine import FlowEngine

router = APIRouter(prefix="/api/flows", tags=["Flow Studio"])

# --- Models for Code Gen/Test ---
class GenerateCodeRequest(BaseModel):
    prompt: str
    # inputs/outputs are optional context, but AI usually overrides them now
    current_inputs: Optional[List[Dict[str, Any]]] = None 
    current_outputs: Optional[List[Dict[str, Any]]] = None

class TestCodeRequest(BaseModel):
    code: str
    inputs: Dict[str, Any]

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
    current_user: UserAuthDetails = Depends(get_current_admin_user), # Admin only
    db: Session = Depends(get_db)
):
    if db.query(DBFlowNodeDefinition).filter(DBFlowNodeDefinition.name == def_data.name).first():
        raise HTTPException(status_code=400, detail="Node type name already exists")
        
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
        
    # Update fields
    node.name = def_data.name
    node.label = def_data.label
    node.description = def_data.description
    node.color = def_data.color
    node.inputs = def_data.inputs
    node.outputs = def_data.outputs
    node.code = def_data.code
    
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

# --- Code Generation & Debugging ---

def extract_json_from_text(text: str):
    """Attempts to find and parse JSON object from a possibly markdown-formatted text."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try finding markdown JSON block
    match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            pass
            
    # Try finding first { and last }
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        try:
            return json.loads(text[start:end+1])
        except:
            pass
            
    return None

@router.post("/generate_code")
def generate_node_design(
    req: GenerateCodeRequest,
    current_user: UserAuthDetails = Depends(get_current_admin_user)
):
    """
    Generates a full node definition (metadata + code) from a user prompt.
    """
    client = build_lollms_client_from_params(current_user.username)
    
    supported_types = "string, int, float, boolean, image, node_ref, model_selection, list, any"
    
    system_prompt = f"""You are an expert Python developer and System Architect for the Lollms Flow Studio.
Your task is to design a custom node based on the user's description.
You MUST output a single valid JSON object containing the node metadata and the Python code implementation.

### JSON Structure
{{
  "name": "snake_case_unique_id",
  "label": "Human Readable Label",
  "description": "A short description of what the node does.",
  "color": "Tailwind CSS classes for background and border (e.g., 'bg-blue-100 dark:bg-blue-900 border-blue-500')",
  "inputs": [
    {{ "name": "input_variable_name", "type": "valid_type" }}
  ],
  "outputs": [
    {{ "name": "output_variable_name", "type": "valid_type" }}
  ],
  "code": "The full python code string (see below)"
}}

### Supported Types for Inputs/Outputs
{supported_types}
- Use 'model_selection' if the node needs to choose a specific LLM model.
- Use 'node_ref' if the node triggers another node (like a loop).
- Use 'image' for base64 encoded image strings.

### Python Code Requirements
1.  **Class Name**: `CustomNode`
2.  **Method**: `def execute(self, inputs, context):`
    *   `inputs`: Dictionary of input values. Keys match your "inputs" definition.
    *   `context`: Access to services.
    *   **Returns**: A dictionary where keys match your "outputs" definition.
3.  **Context Capabilities**:
    *   `context.get_client(model_name=None)`: Returns a LollmsClient. Pass a model name string to use a specific model.
    *   `client.generate_text(prompt, system_prompt=...)`: LLM generation.
    *   `client.tti.generate_image(prompt, width, height)`: Returns bytes. **MUST convert to base64 string** before returning.
    *   `context.engine`: Access to `execute_node_isolated` (only for advanced flow control).
4.  **Libraries**: You may import standard libraries (`json`, `base64`, `random`, `math`, `re`).

### Example Code Structure
```python
import base64
import json

class CustomNode:
    def execute(self, inputs, context):
        # Retrieve input
        prompt = inputs.get("prompt", "")
        
        # Logic
        client = context.get_client()
        result = client.generate_text(prompt)
        
        # Return output
        return {{"text": result}}
```

**IMPORTANT**: Respond ONLY with the JSON object. Do not add conversational text before or after.
"""

    user_prompt = f"Design a node that does the following: {req.prompt}"
    
    generated_text = client.generate_text(user_prompt, system_prompt=system_prompt, max_new_tokens=2048)
    
    # Parse the response
    data = extract_json_from_text(generated_text)
    
    if not data:
        # Fallback: try to just extract code if JSON failed, but we really want the whole object
        raise HTTPException(status_code=500, detail="AI failed to generate a valid JSON node definition. Please try again.")

    # Validate minimal fields
    required_fields = ["name", "label", "inputs", "outputs", "code"]
    for field in required_fields:
        if field not in data:
             raise HTTPException(status_code=500, detail=f"AI generated incomplete definition (missing {field}).")

    return data

@router.post("/test_code")
def test_node_code(
    req: TestCodeRequest,
    current_user: UserAuthDetails = Depends(get_current_admin_user)
):
    """Executes the provided code snippet ephemerally for debugging."""
    try:
        # Create a temporary execution environment
        local_scope = {}
        try:
            exec(req.code, {}, local_scope)
        except Exception as e:
            return {"status": "error", "error": f"Compilation Error: {str(e)}", "traceback": traceback.format_exc()}
        
        NodeClass = local_scope.get("CustomNode")
        if not NodeClass:
            return {"status": "error", "error": "Class 'CustomNode' not found in code."}
            
        # Mock Context
        class MockContext:
            def __init__(self, user):
                self.username = user
                self.lollms_client = None # Lazy load
                self.engine = None 

            def get_client(self, model_name=None):
                # For testing, we just use the default client logic or build one on fly
                if not self.lollms_client:
                     self.lollms_client = build_lollms_client_from_params(self.username, load_llm=True, load_tti=True)
                return self.lollms_client

        context = MockContext(current_user.username)
        node_instance = NodeClass()
        
        # Execute
        try:
            result = node_instance.execute(req.inputs, context)
            
            # Sanitize result for JSON
            display_result = {}
            if isinstance(result, dict):
                for k, v in result.items():
                    if isinstance(v, str) and len(v) > 200:
                        display_result[k] = v[:50] + f"... ({len(v)} chars)"
                    else:
                        display_result[k] = v
            else:
                display_result = result

            return {"status": "success", "output": display_result, "full_output": result} 
            
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

def _execute_flow_task(task: Task, username: str, flow_id: str, graph_data: dict):
    task.log(f"Initializing Flow Engine for user: {username}")
    engine = FlowEngine(username)
    
    task.log("Starting execution...")
    task.set_progress(10)
    
    try:
        results = engine.execute_graph(graph_data)
        task.set_progress(100)
        
        # Serialize results for logging
        serializable_results = {}
        for nid, val in results.items():
            clean_val = {}
            if isinstance(val, dict):
                for k, v in val.items():
                    if isinstance(v, str) and len(v) > 200:
                        clean_val[k] = v[:50] + "... [truncated]"
                    else:
                        clean_val[k] = v
            else:
                clean_val = val
            serializable_results[nid] = clean_val
                
        task.log(f"Execution completed. Results keys: {list(serializable_results.keys())}")
        return serializable_results
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
        args=(current_user.username, flow.id, flow.data),
        description=f"Running workflow {flow.id}",
        owner_username=current_user.username
    )
    return task