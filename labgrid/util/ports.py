from socket import gethostname, socket, AF_INET, SOCK_STREAM
from contextlib import closing

def get_free_port():
    """Helper function to always return an unused port."""
    with closing(socket(AF_INET, SOCK_STREAM)) as s:
        s.bind(('', 0))
        return s.getsockname()[1]
