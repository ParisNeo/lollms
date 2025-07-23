import datetime
from typing import Dict

def replace_keys(text: str, client: Dict[str, str]) -> str:
    """
    Replaces keywords in a string with their dynamic values.
    Keywords are enclosed in curly braces, e.g., {date}.
    """
    if not text:
        return ""
        
    now = datetime.datetime.now()
    keywords = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "user_name": client.get("username", "user"),
    }
    
    # Using a simple loop for clarity, can be optimized with regex for many keys
    for key, value in keywords.items():
        text = text.replace(f"{{{key}}}", str(value))
        
    return text