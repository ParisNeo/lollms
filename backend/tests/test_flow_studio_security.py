import unittest
from unittest.mock import MagicMock
import sys
import os

# Ensure the backend directory is in the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.security import verify_custom_node_code

class TestFlowStudioSecurity(unittest.TestCase):
    def test_safe_code(self):
        """Verify that legitimate, safe custom node code passes validation."""
        safe_code = """
class CustomNode:
    def execute(self, inputs, context):
        text = inputs.get("text", "")
        return {"result": text.upper()}
"""
        is_safe, error_msg = verify_custom_node_code(safe_code)
        self.assertTrue(is_safe)
        self.assertEqual(error_msg, "")

    def test_blocked_import_os(self):
        """Verify that importing blocked modules like 'os' is rejected."""
        unsafe_code = """
import os
class CustomNode:
    def execute(self, inputs, context):
        os.system("whoami")
        return {}
"""
        is_safe, error_msg = verify_custom_node_code(unsafe_code)
        self.assertFalse(is_safe)
        self.assertIn("Import of blocked module 'os' is forbidden", error_msg)

    def test_blocked_import_from_subprocess(self):
        """Verify that 'from ... import ...' of blocked modules is rejected."""
        unsafe_code = """
from subprocess import Popen
class CustomNode:
    def execute(self, inputs, context):
        return {}
"""
        is_safe, error_msg = verify_custom_node_code(unsafe_code)
        self.assertFalse(is_safe)
        self.assertIn("Import from blocked module 'subprocess' is forbidden", error_msg)

    def test_blocked_builtin_eval(self):
        """Verify that using blocked builtins like 'eval' is rejected."""
        unsafe_code = """
class CustomNode:
    def execute(self, inputs, context):
        eval("print('hello')")
        return {}
"""
        is_safe, error_msg = verify_custom_node_code(unsafe_code)
        self.assertFalse(is_safe)
        self.assertIn("Call to blocked function 'eval' is forbidden", error_msg)

    def test_blocked_builtin_exec(self):
        """Verify that using blocked builtins like 'exec' is rejected."""
        unsafe_code = """
class CustomNode:
    def execute(self, inputs, context):
        exec("import os")
        return {}
"""
        is_safe, error_msg = verify_custom_node_code(unsafe_code)
        self.assertFalse(is_safe)
        self.assertIn("Call to blocked function 'exec' is forbidden", error_msg)

    def test_dunder_escape_subclasses(self):
        """Verify that attempting to access dangerous dunder attributes like __subclasses__ is rejected."""
        unsafe_code = """
class CustomNode:
    def execute(self, inputs, context):
        # Classic sandbox escape vector
        for c in ().__class__.__bases__[0].__subclasses__():
            if c.__name__ == 'catch_warnings':
                pass
        return {}
"""
        is_safe, error_msg = verify_custom_node_code(unsafe_code)
        self.assertFalse(is_safe)
        self.assertIn("__subclasses__", error_msg)
        self.assertIn("is forbidden", error_msg)

    def test_dunder_escape_globals(self):
        """Verify that attempting to access dangerous dunder attributes like __globals__ is rejected."""
        unsafe_code = """
class CustomNode:
    def execute(self, inputs, context):
        # Accessing globals of a method
        g = self.execute.__globals__
        return {}
"""
        is_safe, error_msg = verify_custom_node_code(unsafe_code)
        self.assertFalse(is_safe)
        self.assertIn("Access to dangerous attribute '__globals__' is forbidden", error_msg)

    def test_llm_cognitive_audit_pass(self):
        """Verify that the LLM audit layer works and approves safe code when the mock LLM returns safe=true."""
        safe_code = "class CustomNode: pass"
        
        mock_client = MagicMock()
        # Mocking the structured output containing JSON
        mock_client.generate_text.return_value = '{"safe": true, "reason": "Code contains no malicious activities."}'
        
        is_safe, error_msg = verify_custom_node_code(safe_code, mock_client)
        self.assertTrue(is_safe)
        self.assertEqual(error_msg, "")
        mock_client.generate_text.assert_called_once()

    def test_llm_cognitive_audit_fail(self):
        """Verify that the LLM audit layer works and rejects code when the mock LLM returns safe=false."""
        suspicious_code = "class CustomNode: pass"
        
        mock_client = MagicMock()
        mock_client.generate_text.return_value = '{"safe": false, "reason": "Deceptive pattern detected."}'
        
        is_safe, error_msg = verify_custom_node_code(suspicious_code, mock_client)
        self.assertFalse(is_safe)
        self.assertIn("AI Auditor Rejection: Deceptive pattern detected.", error_msg)
        mock_client.generate_text.assert_called_once()

if __name__ == '__main__':
    unittest.main()
