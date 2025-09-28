# backend/utils.py
import socket
from contextlib import closing
import psutil
from backend.settings import settings

def get_local_ip_addresses():
    """Gets all local IPv4 addresses of the machine, including localhost."""
    ip_addresses = []
    try:
        for _, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    ip_addresses.append(addr.address)
        # remove duplicates and return sorted, ensuring localhost is first if present.
        unique_ips = sorted(list(set(ip for ip in ip_addresses)))
        if '127.0.0.1' in unique_ips:
            unique_ips.remove('127.0.0.1')
            unique_ips.insert(0, '127.0.0.1')
        return unique_ips
    except Exception:
        # Fallback in case psutil is not available or fails
        try:
            hostname = socket.gethostname()
            # This can be unreliable, but it's a fallback
            ips = socket.gethostbyname_ex(hostname)[2]
            local_ips = [ip for ip in ips if not ip.startswith("127.")]
            local_ips.insert(0, "127.0.0.1")
            return sorted(list(set(local_ips)))
        except Exception:
            return ["127.0.0.1"]


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