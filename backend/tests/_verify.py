import ast
import sys

p = "backend/tests/test_skills_zoo_readme_traversal_security.py"
try:
    ast.parse(open(p, "rb").read().decode("utf-8"))
    print("SYNTAX OK:", p)
except SyntaxError as e:
    print("SYNTAX ERROR line", e.lineno, e.msg)
    sys.exit(1)