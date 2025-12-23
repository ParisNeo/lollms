# backend/utils.py
import socket
from contextlib import closing
import psutil
import time
from typing import Dict, List, Optional
from backend.settings import settings

# Global in-memory tracking for service usage
# Format: { service_name: { "total_hits": int, "users": { user_id: int } } }
service_usage_stats: Dict[str, Dict] = {
    "openai": {"total_hits": 0, "users": {}},
    "ollama": {"total_hits": 0, "users": {}},
    "lollms": {"total_hits": 0, "users": {}}
}

# Rate limiting tracking: { (identifier, service): [timestamps] }
rate_limit_store: Dict[tuple, list] = {}

def track_service_usage(service: str, user_id: int):
    if service not in service_usage_stats:
        service_usage_stats[service] = {"total_hits": 0, "users": {}}
    
    stats = service_usage_stats[service]
    stats["total_hits"] += 1
    stats["users"][user_id] = stats["users"].get(user_id, 0) + 1

def check_rate_limit(identifier: str, service: str) -> bool:
    """
    Checks if the given identifier (API Key or IP) has exceeded 
    the rate limit configured in settings.
    """
    if not settings.get("rate_limit_enabled", False):
        return True
        
    max_reqs = settings.get("rate_limit_max_requests", 60)
    window = settings.get("rate_limit_window_seconds", 60)
    
    now = time.time()
    key = (identifier, service)
    
    if key not in rate_limit_store:
        rate_limit_store[key] = [now]
        return True
        
    # Clean up old timestamps
    rate_limit_store[key] = [t for t in rate_limit_store[key] if now - t < window]
    
    if len(rate_limit_store[key]) >= max_reqs:
        return False
        
    rate_limit_store[key].append(now)
    return True

def get_local_ip_addresses():
    """Gets all local IPv4 addresses of the machine, including localhost."""
    ip_addresses = []
    try:
        for _, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    ip_addresses.append(addr.address)
        unique_ips = sorted(list(set(ip for ip in ip_addresses)))
        if '127.0.0.1' in unique_ips:
            unique_ips.remove('127.0.0.1')
            unique_ips.insert(0, '127.0.0.1')
        return unique_ips
    except Exception:
        try:
            hostname = socket.gethostname()
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
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            return ip_address
    except Exception:
        return None

def get_accessible_host() -> str:
    """Determines the accessible host for services based on server config."""
    main_server_host = settings.get("host", "0.0.0.0")
    if main_server_host not in ["0.0.0.0", "::"]:
        return main_server_host
    public_domain = settings.get("public_domain_name")
    if public_domain and public_domain.strip():
        return public_domain.strip()
    public_ip = get_public_ip()
    if public_ip:
        return public_ip
    return "localhost"

def find_next_available_port(start_port: int, host: str = "127.0.0.1") -> int:
    """Finds the next available network port starting from a given port."""
    port = start_port
    while True:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                port += 1
