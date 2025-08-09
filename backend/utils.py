# backend/utils.py
import socket
from contextlib import closing
from backend.settings import settings

def get_public_ip():
    """Tries to determine the primary public IP address of the machine."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(2)
            # Doesn't actually send data, just opens a connection to find the preferred interface
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            return ip_address
    except Exception:
        return None

def get_accessible_host() -> str:
    """Determines the accessible host for services based on server config."""
    main_server_host = settings.get("host", "0.0.0.0")

    if main_server_host not in ["0.0.0.0", "::"]:
        # If bound to a specific IP or 'localhost', use that
        return main_server_host

    # If bound to 0.0.0.0, prioritize the configured public domain
    public_domain = settings.get("public_domain_name")
    if public_domain and public_domain.strip():
        return public_domain.strip()

    # If no domain, try to auto-detect the public IP
    public_ip = get_public_ip()
    if public_ip:
        return public_ip
        
    # Fallback to localhost if all else fails
    return "localhost"

def find_next_available_port(start_port: int, host: str = "127.0.0.1") -> int:
    """
    Finds the next available network port starting from a given port.
    """
    port = start_port
    while True:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                port += 1