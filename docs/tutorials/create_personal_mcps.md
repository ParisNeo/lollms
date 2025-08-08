# Tutorial: Creating Your Own Local MCP Server (The Right Way)

This guide will teach you how to build a custom MCP (Model Context Protocol) server to extend the capabilities of Simplified LOLLMS. We'll start with a basic template and then create a practical "Code Utilities" MCP inspired by the example you provided.

## What is an MCP?

An **MCP (Model Calling Protocol)** is a standardized server that exposes a set of "tools" for a Large Language Model (LLM) to use. When an LLM in LOLLMS needs to perform a specific action—like running code, accessing a file, or searching the web—it can call a tool from a connected MCP.

The MCP server handles the request, executes the underlying code for the tool, and returns a structured result to the LLM. This is a powerful way to give your AI new skills.

## Prerequisites

1.  **Python 3.9+** installed.
2.  A code editor like **Visual Studio Code**.
3.  Your **Simplified LOLLMS** application running.
4.  The `lollms-mcp` library, which provides `FastMCP`. To install it, open a terminal and run:
    ```bash
    pip install lollms-mcp
    ```

---

## Part 1: The MCP Boilerplate

Let's start with a minimal, reusable template for any MCP.

### Step 1: Create the Project Structure

Create a folder for your new MCP. We'll call it `my_first_mcp`. Inside, create two files: `server.py` and `description.yaml`.

```text
📁 my_first_mcp/
   ├── 📄 description.yaml
   └── 📄 server.py
```

### Step 2: The `description.yaml` File

This file provides metadata for the LOLLMS UI. It's how your MCP appears in the "Available" and "Installed" lists.

**`description.yaml`:**
```yaml
# The official name of your MCP collection in the UI
name: "My First MCP"

# Your name or alias
author: "Your Name"

# A version number
version: "1.0.0"

# A short description of what this MCP does
description: "A boilerplate for creating new MCPs."

# The category it will appear under in the Zoo
category: "Utilities"
```

### Step 3: The `server.py` Boilerplate

This is the core of your server. We'll use the `FastMCP` library to make it easy.

**`server.py`:**
```python
# ============================================================
# MCP Name      : My First MCP
# Author        : Your Name
# Creation Date : YYYY-MM-DD
# Description   : A boilerplate for creating new MCPs.
# ============================================================
from mcp.server.fastmcp import FastMCP

# 1. Initialize the FastMCP Server
# The name here is for logging purposes.
mcp = FastMCP(name="MyFirstMCPServer")

# 2. Define Your First Tool
# The @mcp.tool() decorator registers a function as a tool that the LLM can call.
@mcp.tool(
    name="hello_world",  # The name the LLM will use to call the tool.
    description="A simple tool that returns a friendly greeting."
)
async def hello_world(text: str) -> str:
    """
    This is the actual Python function that runs when the tool is called.
    
    Args:
        text (str): A string provided by the LLM.

    Returns:
        str: The output that will be sent back to the LLM.
    """
    # Your tool's logic goes here.
    return f"Hello, World! You sent me this text: {text}"

# Add more tools here using the @mcp.tool() decorator...


# 3. Main Entry Point to Run the Server
if __name__ == "__main__":
    # This part allows the server to be run, but LOLLMS will handle it automatically.
    print("MCP server is ready. It should be started via Simplified LOLLMS.")
```

This boilerplate provides a fully functional, albeit simple, MCP server.

---

## Part 2: Creating a "Code Utilities" MCP

Now, let's create a more useful MCP for working with Python code.

### Step 1: Create the Project Structure

Inside your main local MCPs folder (e.g., `C:\lollms_local_mcps`), create a new folder named `code_utilities_mcp`. Inside it, create these files:

```text
📁 code_utilities_mcp/
   ├── 📄 description.yaml
   ├── 📄 requirements.txt
   └── 📄 server.py
```

### Step 2: The `description.yaml`

**`description.yaml`:**
```yaml
name: "Code Utilities"
author: "Your Name"
version: "1.0.0"
description: "A set of tools for checking and analyzing Python code."
category: "Coding"
```

### Step 3: The `requirements.txt`

Our tools will use the `black` library for code formatting.

**`requirements.txt`:**
```text
fastapi
uvicorn[standard]
pydantic
lollms-mcp
black
```

### Step 4: The `server.py`

This server will provide two tools: one to check Python syntax and one to format code.

**`server.py`:**
```python
# ============================================================
# MCP Name      : Code Utilities
# Author        : Your Name
# Creation Date : YYYY-MM-DD
# Description   : Provides tools for checking and formatting Python code.
# ============================================================
from mcp.server.fastmcp import FastMCP
from typing import Dict, Any

# Initialize the FastMCP Server
mcp = FastMCP(name="CodeUtilitiesServer")

@mcp.tool(
    name="check_python_syntax",
    description="Checks if a string of Python code has valid syntax. Does not execute the code."
)
async def check_python_syntax(code: str) -> Dict[str, Any]:
    """
    Checks the syntax of Python code using Python's built-in abstract syntax tree (ast) module.
    
    Args:
        code (str): The Python code to check.

    Returns:
        Dict[str, Any]: A dictionary indicating if the syntax is valid or containing the error.
    """
    import ast
    try:
        ast.parse(code)
        return {"syntax_is_valid": True, "error": None}
    except SyntaxError as e:
        return {"syntax_is_valid": False, "error": f"Syntax error at line {e.lineno}: {e.msg}"}
    except Exception as e:
        return {"syntax_is_valid": False, "error": str(e)}

@mcp.tool(
    name="format_python_code",
    description="Formats Python code using the 'black' code formatter to make it compliant with PEP 8."
)
async def format_python_code(code: str) -> Dict[str, Any]:
    """
    Formats Python code using the black library.
    
    Args:
        code (str): The Python code to format.

    Returns:
        Dict[str, Any]: A dictionary containing the formatted code or an error message.
    """
    try:
        import black
        # Use black's API to format the code string
        formatted_code = black.format_str(code, mode=black.Mode())
        return {"formatted_code": formatted_code, "error": None}
    except ImportError:
        return {"formatted_code": code, "error": "The 'black' library is not installed in this MCP's environment."}
    except Exception as e:
        return {"formatted_code": code, "error": f"An unexpected error occurred during formatting: {str(e)}"}

# Main Entry Point
if __name__ == "__main__":
    print("MCP server is ready. It should be started via Simplified LOLLMS.")
```

---

## Part 3: Adding and Installing Your Local MCPs

The process is the same for both the boilerplate and the code utilities MCP.

1.  **Go to Admin Panel** -> **MCPs Management** -> **Repositories**.
2.  Click **"Add Repository"**.
3.  Select **"Local Folder"**.
4.  Give it a **Name** (e.g., `My Local MCPs`).
5.  Provide the **Full Folder Path** to your main directory (e.g., `C:\lollms_local_mcps`).
6.  Click **"Add Repository"** and then **"Rescan"**.
7.  Go to the **Available** tab. You should see "My First MCP" and "Code Utilities".
8.  Click **"Install"** on the "Code Utilities" MCP. Assign it a port.
9.  Go to the **Installed** tab and **Start (▶)** the "Code Utilities" MCP.

## Part 4: Using Your New Tools

1.  Go to the main chat view.
2.  Enable your tools by clicking the **MCP Tools** button and selecting:
    *   `CodeUtilitiesServer::check_python_syntax`
    *   `CodeUtilitiesServer::format_python_code`
3.  Now, give the AI a task that uses these tools. For example:

    > First, check if this code has valid syntax. If it does, then format it using the black code formatter.
    >
    > ```python
    > def  my_func( x,y) :
    >  if x>y:
    >   return x
    >  else:
    >       return y
    > ```

The AI will first call `check_python_syntax`. Seeing that it's valid, it will then call `format_python_code` and present you with the beautifully formatted result.

You have now mastered the creation and integration of local MCPs! You can expand on this by adding more tools for file operations, web requests, or any other custom logic you can imagine.