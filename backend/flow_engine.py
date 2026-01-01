import traceback
import sys
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from backend.db.models.flow import FlowNodeDefinition
from backend.session import build_lollms_client_from_params
from backend.db import session as db_session_module

class ExecutionContext:
    def __init__(self, engine, username):
        self.engine = engine
        self.username = username
        # Default client (user's preferences)
        self.lollms_client = engine._get_client()

    def get_client(self, model_name: str = None):
        """
        Returns a LollmsClient instance. 
        If model_name is provided, it builds a new client for that model.
        Otherwise returns the default client.
        """
        if not model_name:
            return self.lollms_client
            
        # Parse model_name (binding/model)
        binding_alias = None
        model_part = model_name
        
        if '/' in model_name:
            binding_alias, model_part = model_name.split('/', 1)
            
        return build_lollms_client_from_params(
            self.username,
            binding_alias=binding_alias,
            model_name=model_part,
            load_llm=True
        )

class FlowEngine:
    def __init__(self, username: str):
        self.username = username
        self.logs = []
        self.client = None
        self.node_definitions = {} 
        self._load_definitions()

    def log(self, message):
        print(f"[FlowEngine] {message}")
        self.logs.append(message)

    def _get_client(self):
        if not self.client:
            self.client = build_lollms_client_from_params(
                username=self.username,
                load_llm=True,
                load_tti=True
            )
        return self.client

    def _load_definitions(self):
        db = db_session_module.SessionLocal()
        try:
            defs = db.query(FlowNodeDefinition).all()
            for d in defs:
                self.node_definitions[d.name] = d
        finally:
            db.close()

    def _instantiate_node(self, node_type: str):
        definition = self.node_definitions.get(node_type)
        if not definition:
            raise Exception(f"Unknown node type: {node_type}")
        
        local_scope = {}
        try:
            exec(definition.code, {}, local_scope)
        except Exception as e:
            raise Exception(f"Failed to compile code for {node_type}: {e}")
        
        NodeClass = local_scope.get(definition.class_name)
        if not NodeClass:
            raise Exception(f"Class '{definition.class_name}' not found in code for {node_type}")
            
        return NodeClass()

    def execute_node_isolated(self, node_id: str, inputs: Dict[str, Any]):
        if not hasattr(self, 'current_graph_nodes'):
            raise Exception("Isolated execution requires an active graph context.")
            
        target_node_data = self.current_graph_nodes.get(node_id)
        if not target_node_data:
            raise Exception(f"Target node {node_id} not found in graph.")
            
        final_inputs = {**target_node_data.get('data', {}), **inputs}
        node_instance = self._instantiate_node(target_node_data['type'])
        
        # Pass context with capability to spawn new clients
        context = ExecutionContext(self, self.username)
        
        self.log(f" > Executing isolated node {target_node_data.get('label', 'Node')} ({node_id})")
        return node_instance.execute(final_inputs, context)

    def execute_graph(self, graph_data: Dict[str, Any]):
        nodes = {n['id']: n for n in graph_data.get('nodes', [])}
        self.current_graph_nodes = nodes 
        
        edges = graph_data.get('edges', [])
        
        input_map = {nid: {} for nid in nodes} 
        dependency_counts = {nid: 0 for nid in nodes}
        adjacency = {nid: [] for nid in nodes}

        for edge in edges:
            source = edge['source']
            target = edge['target']
            if source in nodes and target in nodes:
                target_handle = edge['targetHandle']
                source_handle = edge['sourceHandle']
                
                target_node_def = self.node_definitions.get(nodes[target]['type'])
                is_node_ref = False
                if target_node_def:
                    inp_def = next((i for i in target_node_def.inputs if i['name'] == target_handle), None)
                    if inp_def and inp_def.get('type') == 'node_ref':
                        is_node_ref = True

                if is_node_ref:
                    if target not in input_map: input_map[target] = {}
                    input_map[target][target_handle] = source
                else:
                    adjacency[source].append(target)
                    dependency_counts[target] += 1
                    
                    if target not in input_map: input_map[target] = {}
                    input_map[target][target_handle] = {'source': source, 'handle': source_handle}

        queue = [nid for nid, count in dependency_counts.items() if count == 0]
        results = {} 

        while queue:
            node_id = queue.pop(0)
            node_data = nodes[node_id]
            node_type = node_data['type']
            
            node_inputs = node_data.get('data', {}).copy()
            
            connections = input_map.get(node_id, {})
            for handle_name, source_info in connections.items():
                if isinstance(source_info, str): 
                    node_inputs[handle_name] = source_info
                else:
                    source_id = source_info['source']
                    source_handle = source_info['handle']
                    if source_id in results and source_handle in results[source_id]:
                        node_inputs[handle_name] = results[source_id][source_handle]
            
            self.log(f"Executing {node_data.get('label', node_type)}...")
            try:
                node_instance = self._instantiate_node(node_type)
                context = ExecutionContext(self, self.username)
                
                outputs = node_instance.execute(node_inputs, context)
                results[node_id] = outputs
                
            except Exception as e:
                self.log(f"Error executing {node_id}: {e}")
                traceback.print_exc()
                raise e

            for neighbor in adjacency[node_id]:
                dependency_counts[neighbor] -= 1
                if dependency_counts[neighbor] == 0:
                    queue.append(neighbor)

        return results
