import traceback
import sys
import importlib
import json
import os
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from ascii_colors import ASCIIColors

from backend.db import session as db_session_module
from backend.db.models.flow import FlowNodeDefinition
from backend.db.models.user import User as DBUser
from backend.session import build_lollms_client_from_params

class FlowEngine:
    """
    Executes a graph-based workflow defined by the Flow Studio.
    Handles node instantiation, dependency management (auto-install), and execution order.
    """
    def __init__(self, username: str):
        self.username = username
        self.node_instances = {}
        self.results = {}
        self.db_session_factory = db_session_module.SessionLocal
        self._lollms_client = None
        self._is_admin = False
        
        # Determine if user is admin once
        db = self.db_session_factory()
        try:
            u = db.query(DBUser).filter(DBUser.username == username).first()
            if u:
                self._is_admin = u.is_admin
        finally:
            db.close()

    @property
    def lollms_client(self):
        """Lazy load the client with all user-configured capabilities enabled."""
        if not self._lollms_client:
            # Explicitly load all capabilities so nodes have access to TTI, TTS, etc.
            self._lollms_client = build_lollms_client_from_params(
                self.username, 
                load_llm=True, 
                load_tti=True, 
                load_tts=True, 
                load_stt=True
            )
        return self._lollms_client

    def _ensure_requirements(self, node_def: FlowNodeDefinition):
        """Uses pipmaster to dynamically install requirements if missing."""
        if not node_def.requirements:
            return

        import pipmaster
        for req in node_def.requirements:
            if not pipmaster.is_installed(req):
                ASCIIColors.info(f"FlowEngine: Installing requirement '{req}' for node '{node_def.label}'...")
                pipmaster.install(req)

    def execute_node_isolated(self, node_id: str, graph_data: Dict[str, Any], inputs: Dict[str, Any]):
        """Executes a single node, resolving its logic from the database."""
        db = self.db_session_factory()
        try:
            # 1. Find Node in graph
            node_in_graph = next((n for n in graph_data['nodes'] if n['id'] == node_id), None)
            if not node_in_graph:
                raise ValueError(f"Node {node_id} not found in graph data.")

            # 2. Load definition from DB
            node_def = db.query(FlowNodeDefinition).filter(FlowNodeDefinition.name == node_in_graph['type']).first()
            if not node_def:
                raise ValueError(f"Definition for node type '{node_in_graph['type']}' not found.")

            # 3. Handle Dependencies
            self._ensure_requirements(node_def)

            # 4. Instantiate & Execute
            local_scope = {}
            try:
                # Compile code with a filename for better tracebacks
                compiled_code = compile(node_def.code, f"node_logic:{node_def.name}", "exec")
                exec(compiled_code, {}, local_scope)
            except Exception as e:
                error_msg = f"Syntax/Compilation Error in node '{node_def.label}': {str(e)}"
                if self._is_admin:
                    error_msg += f"\n\nTraceback:\n{traceback.format_exc()}"
                raise RuntimeError(error_msg)
            
            NodeClass = local_scope.get(node_def.class_name)
            if not NodeClass:
                raise ValueError(f"Class '{node_def.class_name}' not found in node code.")

            # Context provided to the node
            class NodeContext:
                def __init__(self, engine, owner):
                    self.engine = engine
                    self.lollms_client = engine.lollms_client
                    self.owner_username = owner

                def get_client(self, model_name=None):
                    if not model_name:
                        return self.lollms_client
                    return build_lollms_client_from_params(self.owner_username, model_name=model_name, load_tti=True, load_tts=True)

            context = NodeContext(self, self.username)
            instance = NodeClass()
            
            combined_inputs = {**(node_in_graph.get('data', {})), **inputs}
            
            try:
                return instance.execute(combined_inputs, context)
            except Exception as e:
                # Enhance debugging for admins
                error_prefix = f"Runtime Error in node '{node_def.label}': "
                if self._is_admin:
                    tb = traceback.format_exc()
                    raise RuntimeError(f"{error_prefix}{str(e)}\n\nDetailed Traceback:\n{tb}")
                else:
                    raise RuntimeError(f"{error_prefix}{str(e)}")

        finally:
            db.close()

    def execute_graph(self, graph_data: Dict[str, Any]):
        """Runs the whole graph by resolving dependencies."""
        self.results = {}
        nodes = graph_data.get('nodes', [])
        edges = graph_data.get('edges', [])

        executed_nodes = set()
        
        while len(executed_nodes) < len(nodes):
            progress_made = False
            for node in nodes:
                if node['id'] in executed_nodes:
                    continue

                incoming_edges = [e for e in edges if e['target'] == node['id']]
                can_execute = True
                node_inputs = {}

                for edge in incoming_edges:
                    source_id = edge['source']
                    if source_id not in self.results:
                        can_execute = False
                        break
                    
                    source_res = self.results[source_id]
                    if isinstance(source_res, dict) and edge['sourceHandle'] in source_res:
                        node_inputs[edge['targetHandle']] = source_res[edge['sourceHandle']]
                
                if can_execute:
                    ASCIIColors.info(f"FlowEngine: Executing node {node['id']} ({node['type']})...")
                    # execute_node_isolated handles its own internal error wrapping
                    self.results[node['id']] = self.execute_node_isolated(node['id'], graph_data, node_inputs)
                    executed_nodes.add(node['id'])
                    progress_made = True

            if not progress_made and len(executed_nodes) < len(nodes):
                unexecuted = [n['id'] for n in nodes if n['id'] not in executed_nodes]
                raise RuntimeError(f"Workflow stalled. Unmet dependencies or circular loop for nodes: {unexecuted}")

        return self.results
