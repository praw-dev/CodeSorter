from __future__ import annotations

CONFIG = {"name": "default"}


class Server:
    """Constructed at import time; __init__ reads a module-level function and constant."""

    def __init__(self) -> None:
        self.handler = on_start
        self.name = CONFIG["name"]


def on_start() -> None:
    """A module-level function referenced from Server.__init__ at instantiation time."""
    return None


SERVER = Server()
