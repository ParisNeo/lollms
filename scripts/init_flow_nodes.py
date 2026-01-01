# scripts/init_flow_nodes.py
import sys
import json
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from backend.db import init_database, session as db_session_module
from backend.config import APP_DB_URL
from backend.db.models.flow import FlowNodeDefinition

def populate_nodes():
    print(f"Initializing database connection to {APP_DB_URL}...")
    init_database(APP_DB_URL)
    db = db_session_module.SessionLocal()

    defaults = [
        {
            "name": "input_text",
            "label": "Input Text",
            "description": "Simple text input field",
            "color": "bg-blue-100 dark:bg-blue-900 border-blue-500",
            "inputs": [],
            "outputs": [{"name": "text", "type": "string"}],
            "code": "class CustomNode:\n    def execute(self, inputs, context):\n        return {'text': inputs.get('value', '')}"
        },
        {
            "name": "llm_generate",
            "label": "LLM Text Generator",
            "description": "Generate text using an LLM. Optionally specify a model.",
            "color": "bg-purple-100 dark:bg-purple-900 border-purple-500",
            "inputs": [
                {"name": "system_prompt", "type": "string"},
                {"name": "prompt", "type": "string"},
                {"name": "model", "type": "model_selection"}
            ],
            "outputs": [{"name": "text", "type": "string"}],
            "code": """
class CustomNode:
    def execute(self, inputs, context):
        prompt = inputs.get("prompt", "")
        system = inputs.get("system_prompt", "")
        model_name = inputs.get("model", "")
        
        if not prompt: return {"text": ""}
        
        # Get specific client if model provided, else default
        client = context.get_client(model_name if model_name else None)
        
        return {"text": client.generate_text(prompt, system_prompt=system)}
"""
        },
        {
            "name": "image_generate",
            "label": "Image Generation",
            "description": "Generate an image using TTI",
            "color": "bg-pink-100 dark:bg-pink-900 border-pink-500",
            "inputs": [{"name": "prompt", "type": "string"}],
            "outputs": [{"name": "image", "type": "image"}],
            "code": """
import base64
class CustomNode:
    def execute(self, inputs, context):
        prompt = inputs.get("prompt", "")
        if not prompt: return {"image": ""}
        
        # Use default TTI client
        client = context.get_client()
        if not client.tti:
            return {"image": ""}
        
        img_bytes = client.tti.generate_image(prompt=prompt, width=512, height=512)
        if not img_bytes: return {"image": ""}
        
        b64 = base64.b64encode(img_bytes).decode('utf-8')
        return {"image": b64}
"""
        },
        {
            "name": "text_output",
            "label": "Text Output",
            "description": "Display text result",
            "color": "bg-gray-100 dark:bg-gray-800 border-gray-500",
            "inputs": [{"name": "text", "type": "string"}],
            "outputs": [],
            "code": "class CustomNode:\n    def execute(self, inputs, context):\n        return {'text': inputs.get('text', '')}"
        },
        {
            "name": "combiner",
            "label": "Text Combiner",
            "description": "Concatenates two text inputs",
            "color": "bg-yellow-100 dark:bg-yellow-900 border-yellow-500",
            "inputs": [{"name": "input1", "type": "string"}, {"name": "input2", "type": "string"}],
            "outputs": [{"name": "text", "type": "string"}],
            "code": "class CustomNode:\n    def execute(self, inputs, context):\n        return {'text': f\"{inputs.get('input1', '')}\\n{inputs.get('input2', '')}\"}"
        },
        {
            "name": "loop_executor",
            "label": "Loop (N Times)",
            "description": "Executes a sub-node multiple times.",
            "color": "bg-teal-100 dark:bg-teal-900 border-teal-500",
            "inputs": [{"name": "target_node_id", "type": "node_ref"}, {"name": "count", "type": "int"}, {"name": "start_val", "type": "string"}],
            "outputs": [{"name": "results", "type": "list"}],
            "code": """
class CustomNode:
    def execute(self, inputs, context):
        target_id = inputs.get("target_node_id")
        try:
            count = int(inputs.get("count", 1))
        except:
            count = 1
        val = inputs.get("start_val", "")
        
        if not target_id: return {"results": ["No target"]}
        
        results = []
        for i in range(count):
            step_input = {"value": f"{val} {i+1}", "index": i}
            res = context.engine.execute_node_isolated(target_id, step_input)
            
            # Heuristic to find the 'main' output
            out = res.get('text', res.get('output', res.get('image', str(res))))
            results.append(out)
            
        return {"results": results}
"""
        },
         {
            "name": "image_viewer",
            "label": "Image Viewer",
            "description": "Displays an image result.",
            "color": "bg-gray-100 dark:bg-gray-800 border-gray-500",
            "inputs": [{"name": "image", "type": "image"}],
            "outputs": [],
            "code": "class CustomNode:\n    def execute(self, inputs, context):\n        return {'image': inputs.get('image')}"
        }
    ]

    try:
        count = 0
        for node_def in defaults:
            # Upsert logic
            existing = db.query(FlowNodeDefinition).filter(FlowNodeDefinition.name == node_def["name"]).first()
            if existing:
                existing.label = node_def["label"]
                existing.description = node_def["description"]
                existing.color = node_def["color"]
                existing.inputs = node_def["inputs"]
                existing.outputs = node_def["outputs"]
                existing.code = node_def["code"]
            else:
                new_node = FlowNodeDefinition(**node_def, class_name="CustomNode", is_public=True)
                db.add(new_node)
                count += 1
        
        db.commit()
        print(f"Nodes updated. Added {count} new definitions.")
    except Exception as e:
        print(f"Error seeding nodes: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    populate_nodes()
