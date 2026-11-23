import sys
import traceback

def main():
    try:
        import ast
        src = open("backend/tests/test_skills_zoo_path_traversal_security.py", "rb").read().decode("utf-8")
        ast.parse(src)
        print("TEST FILE: SYNTAX OK")
    except SyntaxError as e:
        print("TEST FILE SYNTAX ERROR line", e.lineno, e.msg)
        return 2

    try:
        from backend.routers.zoos import skills_zoo as mod
        print("IMPORT OK:", mod.__name__)
    except Exception:
        print("IMPORT FAILED:")
        traceback.print_exc()
        return 3

    try:
        import tempfile
        from pathlib import Path
        sys.path.insert(0, "backend/tests")
        import importlib
        tj = importlib.import_module("test_skills_zoo_path_traversal_security")
        with tempfile.TemporaryDirectory() as tmp:
            tj._run_core_checks(Path(tmp))
        print("CORE CHECKS PASSED")
    except Exception:
        print("CORE CHECKS FAILED:")
        traceback.print_exc()
        return 4
    return 0

if __name__ == "__main__":
    sys.exit(main())
</｜DSML｜ parameter>