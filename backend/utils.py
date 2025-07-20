import socket
from contextlib import closing

def find_next_available_port(start_port: int, host: str = "127.0.0.1") -> int:
    """
    Finds the next available network port starting from a given port.

    Args:
        start_port: The port number to start checking from.
        host: The host address to check against. Defaults to '127.0.0.1'.

    Returns:
        The first available port number.
    """
    port = start_port
    while True:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            try:
                s.bind((host, port))
                # If bind is successful, the port is free.
                return port
            except OSError:
                # If bind fails, the port is likely in use, so we increment.
                port += 1